#!/usr/bin/env python3
"""Push many files as ONE commit per repo, via the Git Data API.

The Contents API needs a GET + PUT per file and a separate commit each time;
at 222 files that is 444 round trips. This builds a tree with the file contents
inline and lands a single commit per repo: five calls regardless of file count.
"""
import base64, json, os, sys, time, urllib.error, urllib.parse, urllib.request

TOKEN = open("/home/claude/.ghtok").read().strip()
API = "https://api.github.com"


def call(method, url, body=None, retries=3):
    for attempt in range(retries):
        req = urllib.request.Request(url, method=method,
                                     data=json.dumps(body).encode() if body else None)
        req.add_header("Authorization", "Bearer " + TOKEN)
        req.add_header("Accept", "application/vnd.github+json")
        if body:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.load(r)
        except urllib.error.HTTPError as e:
            d = json.loads(e.read() or b"{}")
            if e.code in (403, 502, 503) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return e.code, d
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            return 0, {"message": str(e)}
    return 0, {"message": "exhausted"}


def is_text(path):
    try:
        open(path, encoding="utf-8").read()
        return True
    except (UnicodeDecodeError, OSError):
        return False


def push_repo(repo, files, message, branch="main"):
    """files: list of (repo_relative_path, local_path)"""
    st, ref = call("GET", f"{API}/repos/{repo}/git/ref/heads/{branch}")
    if st != 200:
        return f"FAIL {repo}: ref {ref.get('message')}"
    head = ref["object"]["sha"]
    st, commit = call("GET", f"{API}/repos/{repo}/git/commits/{head}")
    if st != 200:
        return f"FAIL {repo}: commit {commit.get('message')}"
    base_tree = commit["tree"]["sha"]

    tree = []
    for rel, local in files:
        if is_text(local):
            tree.append(dict(path=rel, mode="100644", type="blob",
                             content=open(local, encoding="utf-8").read()))
        else:
            st, blob = call("POST", f"{API}/repos/{repo}/git/blobs",
                            dict(content=base64.b64encode(open(local, "rb").read()).decode(),
                                 encoding="base64"))
            if st != 201:
                return f"FAIL {repo}: blob {rel} {blob.get('message')}"
            tree.append(dict(path=rel, mode="100644", type="blob", sha=blob["sha"]))

    st, t = call("POST", f"{API}/repos/{repo}/git/trees", dict(base_tree=base_tree, tree=tree))
    if st != 201:
        return f"FAIL {repo}: tree {t.get('message')}"
    st, c = call("POST", f"{API}/repos/{repo}/git/commits",
                 dict(message=message, tree=t["sha"], parents=[head]))
    if st != 201:
        return f"FAIL {repo}: create commit {c.get('message')}"
    st, r = call("PATCH", f"{API}/repos/{repo}/git/refs/heads/{branch}", dict(sha=c["sha"]))
    if st != 200:
        return f"FAIL {repo}: update ref {r.get('message')}"
    return f"ok   {repo}  {c['sha'][:7]}  {len(files)} file(s)"


if __name__ == "__main__":
    plan = json.load(open(sys.argv[1]))
    by_repo = {}
    for p in plan:
        by_repo.setdefault((p["repo"], p["message"]), []).append((p["path"], p["local"]))
    for (repo, msg), files in by_repo.items():
        print(push_repo(repo, files, msg), flush=True)
