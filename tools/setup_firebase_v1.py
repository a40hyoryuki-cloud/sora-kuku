#!/usr/bin/env python3
"""そらのくくランド: Firebase Hosting の初期設定（Cloud Shell で1回だけ実行）

使い方:
  python3 setup_firebase_v1.py stock-screening-496006

やること:
  1. 必要な API を有効化（Firebase / Firebase Hosting / IAM）
  2. GCP プロジェクトに Firebase を追加（追加済みならスキップ）
  3. Hosting のサイト「sora-kuku」を作成（使われていたら別名を試す）
  4. GitHub Actions 用のサービスアカウントと鍵を作成
  5. GitHub に登録する値（鍵）を画面に表示
"""
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

SITE_CANDIDATES = ["sora-kuku", "sora-kuku-land", "sora-kukuland", "sora-kuku-app"]
SA_NAME = "github-sora-kuku"
ROLES = ["roles/firebasehosting.admin", "roles/run.viewer", "roles/serviceusage.apiKeysViewer"]


def sh(cmd, check=True):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and r.returncode != 0:
        print(f"  × コマンド失敗: {cmd}\n{r.stderr.strip()}")
        sys.exit(1)
    return r


def api(method, url, project, token, body=None):
    req = urllib.request.Request(
        url, method=method, data=json.dumps(body or {}).encode(),
        headers={"Authorization": f"Bearer {token}", "x-goog-user-project": project,
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:  # noqa: BLE001
            return e.code, {}


def main():
    if len(sys.argv) < 2:
        print("使い方: python3 setup_firebase_v1.py <GCPプロジェクトID>")
        sys.exit(1)
    pj = sys.argv[1]
    token = sh("gcloud auth print-access-token").stdout.strip()

    print("▶ 1/5 API を有効化…")
    sh(f"gcloud services enable firebase.googleapis.com firebasehosting.googleapis.com "
       f"iam.googleapis.com --project={pj}", check=False)

    print("▶ 2/5 Firebase を追加…")
    code, res = api("POST", f"https://firebase.googleapis.com/v1beta1/projects/{pj}:addFirebase", pj, token)
    if code == 409 or (code >= 400 and "ALREADY_EXISTS" in json.dumps(res)):
        print("  ✓ すでに Firebase プロジェクトです")
    elif code >= 400:
        print(f"  × 失敗 HTTP {code}: {json.dumps(res, ensure_ascii=False)[:400]}")
        sys.exit(1)
    else:
        # 完了まで少し待つ
        for _ in range(30):
            c, r = api("GET", f"https://firebase.googleapis.com/v1beta1/projects/{pj}", pj, token, None)
            if c == 200:
                break
            time.sleep(3)
        print("  ✓ Firebase を追加しました")

    print("▶ 3/5 Hosting サイトを作成…")
    site = None
    c, r = api("GET", f"https://firebasehosting.googleapis.com/v1beta1/projects/{pj}/sites", pj, token)
    have = [s["name"].split("/")[-1] for s in r.get("sites", [])] if c == 200 else []
    for cand in SITE_CANDIDATES:
        if cand in have:
            site = cand
            print(f"  ✓ サイト {cand} は作成済み")
            break
    if not site:
        for cand in SITE_CANDIDATES:
            c, r = api("POST", f"https://firebasehosting.googleapis.com/v1beta1/projects/{pj}/sites?siteId={cand}",
                       pj, token, {})
            if c == 200:
                site = cand
                print(f"  ✓ サイト {cand} を作成しました")
                break
            print(f"  - {cand} は使えませんでした（HTTP {c}）")
    if not site:
        print("  × サイトを作れませんでした。上のエラーを Claude に貼ってください。")
        sys.exit(1)

    print("▶ 4/5 サービスアカウントを作成…")
    sa = f"{SA_NAME}@{pj}.iam.gserviceaccount.com"
    if sh(f"gcloud iam service-accounts describe {sa} --project={pj}", check=False).returncode != 0:
        sh(f'gcloud iam service-accounts create {SA_NAME} --display-name="GitHub deploy (sora-kuku)" --project={pj}')
    for role in ROLES:
        sh(f"gcloud projects add-iam-policy-binding {pj} --member=serviceAccount:{sa} "
           f"--role={role} --condition=None --quiet", check=False)
    keyfile = "sora-kuku-deploy-key.json"
    sh(f"gcloud iam service-accounts keys create {keyfile} --iam-account={sa} --project={pj}")
    print("  ✓ 鍵を作成しました")

    print("\n▶ 5/5 GitHub に登録する値")
    print("=" * 60)
    print(open(keyfile).read().strip())
    print("=" * 60)
    print(f"""
✅ 完了！ サイト名: {site}   公開URL: https://{site}.web.app

次にやること（ブラウザで GitHub）:
  1. https://github.com/a40hyoryuki-cloud/sora-kuku/settings/secrets/actions/new を開く
  2. Name に  FIREBASE_SERVICE_ACCOUNT
  3. Secret に 上の ===== の間の {{ から }} までを全部コピーして貼る → Add secret
  4. 登録できたら、Cloud Shell の鍵ファイルは消してOK:  rm {keyfile}

※ サイト名が sora-kuku 以外になった場合は、その名前を Claude に伝えてください。
""")


if __name__ == "__main__":
    main()
