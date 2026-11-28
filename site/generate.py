#!/usr/bin/env python3
"""Generate the package status page: Menta channels vs Debian (sid / Salsa packaging) vs upstream.
   usage: generate.py <out-dir>        env: GH_TOKEN (optional, raises the GitHub API rate limit)"""
import html, json, os, re, subprocess, sys, urllib.request, urllib.error, datetime

ORG = "menta-linux"
ART = f"{ORG}/artifacts"
# name: (main binary package, debian source name or None, upstream git url)
PKGS = {
 "mate-desktop":             ("mate-desktop", "mate-desktop", "https://github.com/mate-desktop/mate-desktop"),
 "marco":                    ("marco", "marco", "https://github.com/mate-desktop/marco"),
 "mate-settings-daemon":     ("mate-settings-daemon", "mate-settings-daemon", "https://github.com/mate-desktop/mate-settings-daemon"),
 "mate-panel":               ("mate-panel", "mate-panel", "https://github.com/mate-desktop/mate-panel"),
 "caja":                     ("caja", "caja", "https://github.com/mate-desktop/caja"),
 "mate-applets":             ("mate-applets", "mate-applets", "https://github.com/mate-desktop/mate-applets"),
 "mate-media":               ("mate-media", "mate-media", "https://github.com/mate-desktop/mate-media"),
 "mate-power-manager":       ("mate-power-manager", "mate-power-manager", "https://github.com/mate-desktop/mate-power-manager"),
 "mate-notification-daemon": ("mate-notification-daemon", "mate-notification-daemon", "https://github.com/mate-desktop/mate-notification-daemon"),
 "mate-utils":               ("mate-utils", "mate-utils", "https://github.com/mate-desktop/mate-utils"),
 "mate-control-center":      ("mate-control-center", "mate-control-center", "https://github.com/mate-desktop/mate-control-center"),
 "mate-clipboard":           ("mate-clipboard", None, "https://github.com/KeremSoke/mate-clipboard"),
 "mate-fprint":              ("mate-fprint", None, "https://github.com/KeremSoke/mate-fprint"),
 "rojo":                     ("rojo", None, "https://github.com/KeremSoke/rojo"),
 "mate-redshift":            ("mate-redshift", None, "https://github.com/KeremSoke/mate-redshift"),
 "polo":                     ("polo", None, "https://github.com/KeremSoke/polo"),
 "polo-tweaks":              ("polo-tweaks", None, "https://github.com/KeremSoke/polo-tweaks"),
 "menta-plymouth":           ("plymouth-theme-orbit-plane", None, "https://github.com/KeremSoke/menta-plymouth"),
 "gtk-layer-shell":          ("libgtk-layer-shell0", "gtk-layer-shell", "https://github.com/wmww/gtk-layer-shell"),
 "libxfce4windowing":        ("libxfce4windowing-0-0", "libxfce4windowing", "https://gitlab.xfce.org/xfce/libxfce4windowing.git"),
}

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "menta-status"})
    tok = os.environ.get("GH_TOKEN")
    if tok and "api.github.com" in url:
        req.add_header("Authorization", f"Bearer {tok}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()

def channels():
    """{channel: {binary package: version}} from the non-draft releases of the artifacts repo."""
    out = {}
    for rel in json.loads(get(f"https://api.github.com/repos/{ART}/releases?per_page=100")):
        if rel["draft"]:
            continue
        pk = {}
        for a in rel["assets"]:
            m = re.match(r"^([^_]+)_([^_]+)_[^_]+\.deb$", a["name"])
            if m:
                v = m.group(2).replace("%2B", "+")
                pk[m.group(1)] = re.sub(r"\.deb13$", "~deb13", v)   # GitHub turns ~ into . in asset names
        out[rel["tag_name"]] = pk
    return out

STABLE = "trixie"      # current Debian stable

def debian_versions(src):
    """(sid version, stable version) from the Debian archive"""
    if not src: return (None, None)
    try:
        d = json.loads(get(f"https://sources.debian.org/api/src/{src}/"))
    except Exception:
        return (None, None)
    sid = stable = None
    for v in d.get("versions", []):
        suites = v.get("suites", [])
        if "sid" in suites: sid = v["version"]
        if any(x == STABLE or x.startswith(STABLE + "-") for x in suites): stable = v["version"]
    return (sid, stable)

def salsa_head(src):
    if not src: return None
    for br in ("master", "debian/latest", "debian/master"):
        try:
            t = get(f"https://salsa.debian.org/debian-mate-team/{src}/-/raw/{br}/debian/changelog")
            m = re.match(r"^\S+ \(([^)]+)\)", t)
            if m: return m.group(1)
        except Exception:
            continue
    return None

def vkey(v):
    return [int(x) if x.isdigit() else x for x in re.split(r"[.]", v)]

def upstream(url):
    """(latest tag version or None, head short hash)"""
    tags = subprocess.run(["git", "ls-remote", "--tags", "--refs", url], capture_output=True, text=True).stdout
    vers = []
    for line in tags.splitlines():
        t = line.split("refs/tags/")[-1]
        m = re.match(r"^(?:[A-Za-z][A-Za-z0-9._-]*-)?v?(\d+(?:\.\d+)+)$", t)
        if m: vers.append(m.group(1))
    vers.sort(key=lambda v: [int(x) for x in v.split(".")])
    head = subprocess.run(["git", "ls-remote", url, "HEAD"], capture_output=True, text=True).stdout.split()
    return (vers[-1] if vers else None, head[0][:7] if head else None)

def base(v):
    """upstream part of a Debian version: strip epoch/revision/+git suffix"""
    if not v: return None
    v = re.sub(r"^\d+:", "", v)
    v = v.rsplit("-", 1)[0] if "-" in v else v
    return v.split("+")[0].split("~")[0]

def status(menta, up_tag):
    if not menta: return ("none", "not in this channel")
    if "+git" in menta: return ("snap", "git snapshot")
    b, u = base(menta), up_tag
    if not u or not b: return ("snap", "no upstream release")
    try:
        k1 = [int(x) for x in re.findall(r"\d+", b)]; k2 = [int(x) for x in u.split(".")]
    except Exception:
        return ("snap", "")
    if k1 >= k2: return ("ok", "at upstream")
    return ("old", f"upstream {u}")

def esc(x): return html.escape(x) if x else "&ndash;"

def main(out):
    os.makedirs(out, exist_ok=True)
    ch = channels()
    names = sorted(ch, key=lambda c: (c != "stable", c != "testing", c))   # stable, testing, unstable, ...
    rows, data = [], []
    for repo, (binpkg, dsrc, uurl) in PKGS.items():
        tag, head = upstream(uurl)
        sid, deb_stable = debian_versions(dsrc); salsa = salsa_head(dsrc)
        cells = []
        for c in names:
            v = ch[c].get(binpkg)
            cls, note = status(v, tag)
            cells.append((c, v, cls, note))
        data.append({"package": repo, "channels": {c: v for c, v, _, _ in cells}, "debian_stable": deb_stable, "debian_sid": sid, "salsa": salsa,
                     "upstream_tag": tag, "upstream_head": head, "upstream": uurl})
        tds = "".join(f'<td class="{cls}" title="{html.escape(note)}">{esc(v)}</td>' for _, v, cls, note in cells)
        up = f'<a href="{uurl}">{esc(tag) if tag else "HEAD"}</a>' + (f' <span class="m">@{head}</span>' if head else "")
        rows.append(f'<tr><th><a href="https://github.com/{ORG}/pkg-{repo}">{repo}</a></th>{tds}<td>{esc(deb_stable)}</td><td>{esc(sid)}</td><td>{esc(salsa)}</td><td>{up}</td></tr>')
    head_cells = "".join(f"<th>{html.escape(c)}</th>" for c in names)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = f"""<!doctype html><meta charset="utf-8"><title>Menta Linux packages</title>
<style>body{{font:14px system-ui,sans-serif;margin:2em;color:#222}}table{{border-collapse:collapse}}
th,td{{border:1px solid #ddd;padding:.35em .6em;text-align:left}}thead th{{background:#f3f3f3}}
td.ok{{background:#e6f6e6}}td.old{{background:#fde8e8}}td.snap{{background:#fff6dc}}td.none{{color:#999}}
.m{{color:#888;font-size:12px}}a{{color:#0a58ca;text-decoration:none}}</style>
<h1>Menta Linux packages</h1>
<p>Channels come from the releases of <a href="https://github.com/{ART}">{ART}</a> (published through the
<a href="https://menta-linux.github.io/apt/">apt repository</a>). <b>stable</b> holds the Debian 13 (trixie) builds (versions end in <code>~deb13</code>); <b>unstable</b> holds the sid builds (Debian testing/unstable). <code>gtk-layer-shell</code> and <code>libxfce4windowing</code> are Menta backports that only the stable channel needs. <b>Debian stable ({STABLE})</b> and <b>Debian sid</b> are the versions in the Debian archive,
<b>Salsa</b> is the top of <code>debian/changelog</code> on salsa.debian.org/debian-mate-team, <b>Upstream</b> is the latest tag
(and HEAD) of the upstream project. Cell colours: green = at the latest upstream release, yellow = git snapshot,
red = behind the latest upstream tag.</p>
<table><thead><tr><th>Package</th>{head_cells}<th>Debian stable ({STABLE})</th><th>Debian sid</th><th>Salsa</th><th>Upstream</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<p class="m">Generated {now}. <a href="packages.json">packages.json</a></p>"""
    open(os.path.join(out, "index.html"), "w").write(page)
    json.dump({"generated": now, "channels": names, "packages": data}, open(os.path.join(out, "packages.json"), "w"), indent=1)
    print(f"{len(rows)} packages, channels: {names}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "public")
