#!/usr/bin/env python3
"""Gera manifesto publico seguro apos uma release publicada no GitHub."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

EXPECTED_PACKAGE = "br.com.dennyximenes.meufluxo"


def build_manifest(tag: str, body: str, repo: str, apk_dir: Path, old: dict | None):
    version_match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)", tag)
    if not version_match:
        raise ValueError("Tag invalida; use v1.0.6")
    m = re.search(r"(?im)^\s*C[oó]digo\s*:\s*(\d+)\s*$", body)
    if not m:
        raise ValueError("Descricao da release deve conter 'Código: 7' em uma linha")
    code = int(m.group(1))
    if code < 1:
        raise ValueError("versionCode invalido")
    version = tag[1:]
    if old:
        if int(old.get('latestVersionCode', 0)) >= code:
            raise ValueError("Nova release nao tem versionCode maior que a anterior")
    apks = list(apk_dir.glob('*.apk'))
    if len(apks) != 1:
        raise ValueError(f"Esperado exatamente um APK no release, recebido: {len(apks)}")
    apk = apks[0]
    expected = f"MeuFluxo-{version}.apk"
    if apk.name != expected:
        raise ValueError(f"Nome do APK deve ser {expected}")
    with zipfile.ZipFile(apk, 'r') as z:
        if z.testzip() is not None:
            raise ValueError("APK corrompido")
        names = set(z.namelist())
        if not {'AndroidManifest.xml', 'classes.dex', 'assets/index.html'}.issubset(names):
            raise ValueError("Arquivos obrigatorios do APK ausentes")
    sha = hashlib.sha256(apk.read_bytes()).hexdigest()
    url = f"https://github.com/{repo}/releases/download/{quote(tag)}/{quote(apk.name)}"
    return {
        "appId": EXPECTED_PACKAGE,
        "latestVersionCode": code,
        "latestVersionName": version,
        "apkUrl": url,
        "sha256": sha,
        "releaseNotes": f"Correcoes e melhorias do Meu Fluxo {version}",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--tag', required=True)
    p.add_argument('--repo', required=True)
    p.add_argument('--release-json', type=Path, required=True)
    p.add_argument('--apk-dir', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args=p.parse_args()
    release=json.loads(args.release_json.read_text(encoding='utf-8'))
    if release.get('tagName') != args.tag or release.get('isDraft') or release.get('isPrerelease'):
        raise ValueError("Release nao publicada, prerelease ou tag divergente")
    old=json.loads(args.output.read_text(encoding='utf-8')) if args.output.exists() else None
    result=build_manifest(args.tag, release.get('body') or '', args.repo, args.apk_dir, old)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f"Atualizacao validada: {result['latestVersionName']} / codigo {result['latestVersionCode']}")
    print(f"SHA-256: {result['sha256']}")

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)
