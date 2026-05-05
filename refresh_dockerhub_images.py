#!/usr/bin/env python3
"""
refresh_dockerhub_images.py

Scans the repository for Dockerfiles and (optionally) main.yaml files that map Dockerfiles to Docker Hub image names.
If a remote Docker Hub image tag is older than a threshold (in days), the script builds the image, pushes it to Docker Hub,
then removes the local image and prunes the builder cache.

Usage:
  python3 refresh_dockerhub_images.py --root . --namespace myorg --threshold-days 30 \
      --dockerhub-username USER --dockerhub-password PASS [--dry-run]

Requirements:
  pip install requests pyyaml

Notes:
  - If a folder contains main.yaml or main.yml, the script will try to read an image name from keys: image, name, repo, repository, image_name.
    If the image value includes a tag (repo:tag) that tag will be used; otherwise a 'tag' key or 'latest' is used.
  - If no main.yaml is present the script falls back to using <namespace>/<directory_name>:latest (namespace required in that case).
  - Docker must be installed and the user must have rights to build and push images.
"""

import argparse
import os
import sys
import subprocess
import logging
import json
import base64
import shutil
from datetime import datetime, timezone

# dependencies
try:
    import requests
except Exception:
    print("Missing dependency 'requests'. Install with: pip install requests")
    sys.exit(2)
try:
    import yaml
except Exception:
    print("Missing dependency 'PyYAML'. Install with: pip install pyyaml")
    sys.exit(2)


def find_dockerfiles(root):
    dockerfiles = []
    for dirpath, dirs, files in os.walk(root):
        for f in files:
            if f.lower() == 'dockerfile':
                dockerfiles.append(os.path.join(dirpath, f))
    return dockerfiles


def load_main_yaml(dirpath):
    for name in ('main.yaml', 'main.yml'):
        path = os.path.join(dirpath, name)
        if os.path.exists(path):
            try:
                with open(path, 'r') as fh:
                    data = yaml.safe_load(fh) or {}
                return data
            except Exception as e:
                logging.warning('Failed to parse %s: %s', path, e)
    return None


def parse_main_yaml_builds(data):
    """
    Parse main.yaml structure and return list of build dicts:
      [{'dockerfile': 'Dockerfile', 'repo': 'namespace/repo', 'tags': ['tag1','tag2']}, ...]
    Returns None if no usable info found.
    """
    if not data or not isinstance(data, dict):
        return None
    builds = []
    top_image = data.get('image') or data.get('repo') or data.get('name')
    base_repo = None
    if isinstance(top_image, str):
        s = top_image.strip()
        if ':' in s:
            base_repo, tag = s.rsplit(':', 1)
            # If no explicit builds list, create a single build entry using optional dockerfile or default Dockerfile
            if not data.get('builds'):
                dockerfile = data.get('dockerfile') or 'Dockerfile'
                builds.append({'dockerfile': dockerfile, 'repo': base_repo, 'tags': [tag]})
                return builds
        else:
            base_repo = s

    if data.get('builds') and isinstance(data['builds'], list):
        for entry in data['builds']:
            if isinstance(entry, str):
                # simple string entries not supported
                continue
            dockerfile = entry.get('dockerfile') or entry.get('file') or entry.get('path') or 'Dockerfile'
            tags = []
            t = entry.get('tags') or entry.get('tag')
            if isinstance(t, list):
                tags = [str(x) for x in t if x]
            elif isinstance(t, str):
                tags = [t]
            entry_image = entry.get('image')
            repo = entry_image or base_repo
            if isinstance(repo, str) and ':' in repo:
                r, tag = repo.rsplit(':', 1)
                repo = r
                if not tags:
                    tags = [tag]
            builds.append({'dockerfile': dockerfile, 'repo': repo, 'tags': tags})
        return builds

    # fallback: single image with top-level tag
    if base_repo:
        tag = data.get('tag')
        if tag:
            dockerfile = data.get('dockerfile') or 'Dockerfile'
            builds.append({'dockerfile': dockerfile, 'repo': base_repo, 'tags': [tag]})
            return builds
    return None


def image_from_yaml(data):
    if not data or not isinstance(data, dict):
        return None, None
    for key in ('image', 'name', 'repository', 'repo', 'image_name'):
        val = data.get(key)
        if val:
            s = str(val).strip()
            if ':' in s:
                repo, tag = s.rsplit(':', 1)
                return repo, tag
            else:
                tag = data.get('tag') or 'latest'
                return s, tag
    tags = data.get('tags')
    if isinstance(tags, list) and tags:
        tag = str(tags[0])
        repo = data.get('repo') or data.get('name') or data.get('repository')
        if repo:
            return repo, tag
    return None, None


def get_local_docker_credentials(registry='https://index.docker.io/v1/'):
    """
    Try to extract Docker Hub credentials from ~/.docker/config.json or via docker credential helper.
    Returns (username, password_or_token) or (None, None) if not found.
    """
    config_path = os.path.expanduser('~/.docker/config.json')
    if not os.path.exists(config_path):
        return None, None
    try:
        with open(config_path, 'r') as fh:
            cfg = json.load(fh)
    except Exception as e:
        logging.warning('Failed to read docker config: %s', e)
        return None, None
    auths = cfg.get('auths', {})
    keys = [registry, 'https://registry-1.docker.io/', 'registry-1.docker.io', 'https://index.docker.io/v1/', 'docker.io']
    for k in keys:
        entry = auths.get(k)
        if entry:
            auth = entry.get('auth')
            if auth:
                try:
                    decoded = base64.b64decode(auth).decode()
                    if ':' in decoded:
                        u, p = decoded.split(':', 1)
                        return u, p
                except Exception:
                    pass
            identity = entry.get('IdentityToken') or entry.get('identitytoken')
            if identity:
                # IdentityToken may be a bearer token; return it as password with unknown username
                return None, identity

    creds_store = cfg.get('credsStore')
    cred_helpers = cfg.get('credHelpers', {})
    helper = None
    for k in keys:
        h = cred_helpers.get(k)
        if h:
            helper = h
            break
    if not helper and creds_store:
        helper = creds_store
    if helper:
        helper_bin = f'docker-credential-{helper}'
        if shutil.which(helper_bin):
            try:
                proc = subprocess.run([helper_bin, 'get'], input=registry.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                out = proc.stdout.decode()
                j = json.loads(out)
                uname = j.get('Username') or j.get('username')
                secret = j.get('Secret') or j.get('secret') or j.get('Password')
                if uname and secret:
                    return uname, secret
            except Exception as e:
                logging.warning('Credential helper %s failed: %s', helper_bin, e)

    # try docker info to get username (no password)
    try:
        out = run_cmd(['docker', 'info', '--format', '{{.Username}}'], check=False)
        uname = out.strip()
        if uname:
            return uname, None
    except Exception:
        pass

    return None, None


def dockerhub_get_token(username, password):
    try:
        r = requests.post('https://hub.docker.com/v2/users/login/', json={'username': username, 'password': password}, timeout=30)
        if r.ok:
            return r.json().get('token')
        logging.warning('Login failed: %s %s', r.status_code, r.text[:200])
    except Exception as e:
        logging.warning('Exception during login: %s', e)
    return None


def get_tag_last_updated(image_repo, tag, token=None):
    # image_repo like 'namespace/repo' or 'repo'
    if image_repo.startswith('docker.io/'):
        image_repo = image_repo.replace('docker.io/', '')
    if '/' in image_repo:
        namespace, repo = image_repo.split('/', 1)
    else:
        namespace = 'library'
        repo = image_repo
    headers = {}
    if token:
        headers['Authorization'] = f'JWT {token}'

    url = f'https://hub.docker.com/v2/repositories/{namespace}/{repo}/tags/{tag}/'
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code == 200:
            data = r.json()
            return data.get('last_updated')
        elif r.status_code == 404:
            # fallback: list tags and search
            list_url = f'https://hub.docker.com/v2/repositories/{namespace}/{repo}/tags?page_size=100'
            r2 = requests.get(list_url, headers=headers, timeout=30)
            if r2.ok:
                for res in r2.json().get('results', []):
                    if res.get('name') == tag:
                        return res.get('last_updated')
            return None
        else:
            logging.warning('Hub API returned %s for %s/%s:%s', r.status_code, namespace, repo, tag)
            return None
    except Exception as e:
        logging.warning('Failed to query hub for %s/%s:%s - %s', namespace, repo, tag, e)
        return None


def parse_iso(s):
    if not s:
        return None
    try:
        if s.endswith('Z'):
            s = s[:-1] + '+00:00'
        return datetime.fromisoformat(s)
    except Exception:
        # last_updated format may vary; give up
        return None


def run_cmd(cmd, check=True, input_data=None):
    logging.debug('Running: %s', ' '.join(cmd))
    p = subprocess.run(cmd, input=input_data, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = p.stdout.decode(errors='replace')
    if p.returncode != 0 and check:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{out}")
    return out


def build_and_push(dockerfile, context, full_image, dry_run=False, cleanup=True):
    print(f"Building {full_image} (Dockerfile: {dockerfile})")
    if dry_run:
        return True
    build_cmd = ['docker', 'build', '-f', dockerfile, '-t', full_image, context]
    try:
        run_cmd(build_cmd, check=True)
    except Exception as e:
        logging.error('Build failed for %s: %s', full_image, e)
        return False
    try:
        run_cmd(['docker', 'push', full_image], check=True)
    except Exception as e:
        logging.error('Push failed for %s: %s', full_image, e)
        return False
    if cleanup:
        try:
            run_cmd(['docker', 'image', 'rm', '-f', full_image], check=False)
        except Exception:
            pass
        try:
            run_cmd(['docker', 'builder', 'prune', '-f'], check=False)
        except Exception:
            pass
    return True


def build_and_push_tags(dockerfile, context, repo, tags, dry_run=False, cleanup=True):
    """
    Build once using the first tag and push all tags (tagging the built image).
    tags: list of tag strings (at least one)
    """
    if not tags:
        logging.info('No tags provided for %s; skipping build', repo)
        return True
    first_tag = tags[0]
    full_image = f"{repo}:{first_tag}"
    # Build with no cleanup so we can tag additional tags
    if dry_run:
        logging.info('DRY RUN: would build %s from %s', full_image, dockerfile)
        for t in tags[1:]:
            logging.info('DRY RUN: would tag %s as %s:%s', full_image, repo, t)
        return True
    ok = build_and_push(dockerfile, context, full_image, dry_run=False, cleanup=False)
    if not ok:
        return False
    # tag and push remaining tags
    for tag in tags[1:]:
        target = f"{repo}:{tag}"
        try:
            run_cmd(['docker', 'tag', full_image, target], check=True)
            run_cmd(['docker', 'push', target], check=True)
        except Exception as e:
            logging.error('Failed to tag/push %s: %s', target, e)
            return False
    if cleanup:
        for tag in tags:
            try:
                run_cmd(['docker', 'image', 'rm', '-f', f"{repo}:{tag}"], check=False)
            except Exception:
                pass
        try:
            run_cmd(['docker', 'builder', 'prune', '-f'], check=False)
        except Exception:
            pass
    return True


def main():
    parser = argparse.ArgumentParser(description='Refresh Docker Hub images by rebuilding stale images')
    parser.add_argument('--root', default='.', help='Repository root to scan for Dockerfiles')
    parser.add_argument('--namespace', help='Docker Hub namespace/org to use when main.yaml is missing')
    parser.add_argument('--threshold-days', '-t', type=int, default=30, help='Age in days to consider an image stale')
    parser.add_argument('--dockerhub-username', default=os.environ.get('DOCKERHUB_USERNAME'), help='Docker Hub username (or set DOCKERHUB_USERNAME env)')
    parser.add_argument('--dockerhub-password', default=os.environ.get('DOCKERHUB_PASSWORD'), help='Docker Hub password/token (or set DOCKERHUB_PASSWORD env)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without building/pushing')
    parser.add_argument('--no-cleanup', dest='cleanup', action='store_false', help='Do not remove local image or prune cache after push')

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    # ensure docker available
    try:
        run_cmd(['docker', '--version'], check=True)
    except Exception as e:
        logging.error('Docker CLI not found or not working: %s', e)
        sys.exit(2)

    token = None
    # Prefer explicit credentials, but fall back to local docker login info when available
    if args.dockerhub_username and args.dockerhub_password:
        token = dockerhub_get_token(args.dockerhub_username, args.dockerhub_password)
        # also login docker CLI for push (best-effort)
        try:
            run_cmd(['docker', 'login', '-u', args.dockerhub_username, '--password-stdin'], check=True, input_data=args.dockerhub_password.encode())
        except Exception as e:
            logging.warning('docker login failed: %s', e)
    else:
        # Try to use system Docker credentials from ~/.docker/config.json or credential helper
        local_user, local_pwd = get_local_docker_credentials()
        if local_user and local_pwd:
            # we have both username and password/token
            token = dockerhub_get_token(local_user, local_pwd)
            try:
                # try logging in with extracted credentials (best-effort)
                if local_pwd:
                    run_cmd(['docker', 'login', '-u', local_user, '--password-stdin'], check=True, input_data=local_pwd.encode())
            except Exception as e:
                logging.debug('docker login with local creds failed: %s', e)
        elif local_user and not local_pwd:
            logging.info('Found local docker username (%s) but no password/token; relying on existing docker CLI auth for pushes', local_user)
        else:
            logging.info('No docker credentials provided or found; proceeding unauthenticated (public repos only)')

    dockerfiles = find_dockerfiles(args.root)
    if not dockerfiles:
        logging.info('No Dockerfile found under %s', args.root)
        return

    now = datetime.now(timezone.utc)
    to_rebuild = []

    for df in dockerfiles:
        ddir = os.path.dirname(df)
        data = load_main_yaml(ddir)
        builds = parse_main_yaml_builds(data)
        if builds:
            for build in builds:
                repo = build.get('repo')
                tags = build.get('tags') or []
                dockerfile_name = build.get('dockerfile') or 'Dockerfile'
                dockerfile_path = dockerfile_name if os.path.isabs(dockerfile_name) else os.path.join(ddir, dockerfile_name)
                if not repo:
                    if not args.namespace:
                        logging.warning('No repo found for build in %s and no --namespace provided -> skipping', dockerfile_path)
                        continue
                    repo_name = os.path.basename(ddir)
                    repo = f"{args.namespace}/{repo_name}"
                if not tags:
                    tags = ['latest']
                for tag in tags:
                    logging.info('Checking %s:%s (dockerfile=%s)', repo, tag, dockerfile_path)
                    last_updated = get_tag_last_updated(repo, tag, token=token)
                    if last_updated:
                        dt = parse_iso(last_updated)
                        if dt:
                            age_days = (now - dt).total_seconds() / 86400.0
                            logging.info('Last updated: %s (%.1f days old)', last_updated, age_days)
                            if age_days >= args.threshold_days:
                                found = None
                                for t in to_rebuild:
                                    if t['dockerfile'] == dockerfile_path and t['repo'] == repo and t['context'] == ddir:
                                        found = t
                                        break
                                if found:
                                    if tag not in found['tags']:
                                        found['tags'].append(tag)
                                else:
                                    to_rebuild.append({'dockerfile': dockerfile_path, 'context': ddir, 'repo': repo, 'tags': [tag]})
                            else:
                                logging.info('Skipping %s:%s (fresh)', repo, tag)
                        else:
                            logging.info('Could not parse last_updated for %s:%s, scheduling rebuild', repo, tag)
                            found = None
                            for t in to_rebuild:
                                if t['dockerfile'] == dockerfile_path and t['repo'] == repo and t['context'] == ddir:
                                    found = t
                                    break
                            if found:
                                if tag not in found['tags']:
                                    found['tags'].append(tag)
                            else:
                                to_rebuild.append({'dockerfile': dockerfile_path, 'context': ddir, 'repo': repo, 'tags': [tag]})
                    else:
                        logging.info('No remote tag info for %s:%s, scheduling build', repo, tag)
                        found = None
                        for t in to_rebuild:
                            if t['dockerfile'] == dockerfile_path and t['repo'] == repo and t['context'] == ddir:
                                found = t
                                break
                        if found:
                            if tag not in found['tags']:
                                found['tags'].append(tag)
                        else:
                            to_rebuild.append({'dockerfile': dockerfile_path, 'context': ddir, 'repo': repo, 'tags': [tag]})
        else:
            image_repo, tag = image_from_yaml(data)
            if not image_repo:
                if not args.namespace:
                    logging.warning('No main.yaml and no --namespace provided for Dockerfile %s -> skipping', df)
                    continue
                repo_name = os.path.basename(ddir)
                image_repo = f"{args.namespace}/{repo_name}"
                tag = 'latest'

            if not tag:
                tag = 'latest'

            logging.info('Checking %s:%s (dockerfile=%s)', image_repo, tag, df)
            last_updated = get_tag_last_updated(image_repo, tag, token=token)
            if last_updated:
                dt = parse_iso(last_updated)
                if dt:
                    age_days = (now - dt).total_seconds() / 86400.0
                    logging.info('Last updated: %s (%.1f days old)', last_updated, age_days)
                    if age_days >= args.threshold_days:
                        to_rebuild.append({'dockerfile': df, 'context': ddir, 'repo': image_repo, 'tags': [tag]})
                    else:
                        logging.info('Skipping %s:%s (fresh)', image_repo, tag)
                else:
                    logging.info('Could not parse last_updated for %s:%s, scheduling rebuild', image_repo, tag)
                    to_rebuild.append({'dockerfile': df, 'context': ddir, 'repo': image_repo, 'tags': [tag]})
            else:
                logging.info('No remote tag info for %s:%s, scheduling build', image_repo, tag)
                to_rebuild.append({'dockerfile': df, 'context': ddir, 'repo': image_repo, 'tags': [tag]})

    if not to_rebuild:
        logging.info('No images require rebuilding')
        return

    logging.info('Build entries to rebuild: %d', len(to_rebuild))
    for task in to_rebuild:
        dockerfile = task['dockerfile']
        ctx = task['context']
        repo = task['repo']
        tags = task['tags']
        try:
            ok = build_and_push_tags(dockerfile, ctx, repo, tags, dry_run=args.dry_run, cleanup=args.cleanup)
            if ok:
                logging.info('Successfully refreshed %s tags %s', repo, ','.join(tags))
            else:
                logging.error('Failed to refresh %s tags %s', repo, ','.join(tags))
        except Exception as e:
            logging.exception('Error rebuilding %s tags %s: %s', repo, ','.join(tags), e)


if __name__ == '__main__':
    main()
