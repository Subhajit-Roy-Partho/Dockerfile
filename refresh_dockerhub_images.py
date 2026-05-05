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
    if args.dockerhub_username and args.dockerhub_password:
        token = dockerhub_get_token(args.dockerhub_username, args.dockerhub_password)
        # also login docker CLI for push
        try:
            run_cmd(['docker', 'login', '-u', args.dockerhub_username, '--password-stdin'], check=True, input_data=args.dockerhub_password.encode())
        except Exception as e:
            logging.warning('docker login failed: %s', e)

    dockerfiles = find_dockerfiles(args.root)
    if not dockerfiles:
        logging.info('No Dockerfile found under %s', args.root)
        return

    now = datetime.now(timezone.utc)
    to_rebuild = []

    for df in dockerfiles:
        ddir = os.path.dirname(df)
        data = load_main_yaml(ddir)
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
                    to_rebuild.append((df, ddir, image_repo, tag))
                else:
                    logging.info('Skipping %s:%s (fresh)', image_repo, tag)
            else:
                logging.info('Could not parse last_updated for %s:%s, scheduling rebuild', image_repo, tag)
                to_rebuild.append((df, ddir, image_repo, tag))
        else:
            logging.info('No remote tag info for %s:%s, scheduling build', image_repo, tag)
            to_rebuild.append((df, ddir, image_repo, tag))

    if not to_rebuild:
        logging.info('No images require rebuilding')
        return

    logging.info('Images to rebuild: %d', len(to_rebuild))
    for df, ctx, repo, tag in to_rebuild:
        full_image = f"{repo}:{tag}"
        try:
            ok = build_and_push(df, ctx, full_image, dry_run=args.dry_run, cleanup=args.cleanup)
            if ok:
                logging.info('Successfully refreshed %s', full_image)
            else:
                logging.error('Failed to refresh %s', full_image)
        except Exception as e:
            logging.exception('Error rebuilding %s: %s', full_image, e)


if __name__ == '__main__':
    main()
