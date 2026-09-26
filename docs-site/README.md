# eGRM user guide (source)

The end-user guide served at **`/guide`** on every eGRM site. It is written for
citizens and government staff, not for developers — there is no repo link, no
"copy as markdown" button, and no API reference in it.

It is a [fumadocs](https://fumadocs.dev) site exported to static HTML. The
export is committed to `egrm/public/guide/`, so the guide ships with the app:
deploying eGRM deploys the matching guide, with no separate docs host to keep
in sync.

## Layout

| Path | What it is |
| --- | --- |
| `content/docs/` | The pages, as MDX. This is what you edit. |
| `content/docs/img/` | Screenshots, imported relatively from the MDX. |
| `scripts/` | Playwright capture scripts that produce those screenshots. |
| `../egrm/public/guide/` | The committed build output. Never edit by hand. |
| `../egrm/utils/guide_page.py` | Serves the export at `/guide`. |

## Editing and publishing

```bash
npm install          # first time only
npm run dev          # http://localhost:3000/guide
npm run build        # static export into ./out
rm -rf ../egrm/public/guide && cp -R out ../egrm/public/guide
```

Commit both the MDX change and the rebuilt `egrm/public/guide/`. On the server,
`git pull` plus `bench restart` is enough — there is no node build step there.

`basePath` is `/guide` but `assetPrefix` is `/assets/egrm/guide`: pages go
through Frappe (which is what resolves a directory URL to `index.html`), while
JS, CSS and images are served straight off disk by nginx.

## Screenshots

```bash
python3 scripts/capture.py                      # public portal + login
EGRM_LANG=en python3 scripts/capture_flow.py    # the submit wizard, step by step
EGRM_USER=... EGRM_PASS=... python3 scripts/capture_staff.py   # the desk
```

They run against `EGRM_BASE` (default `https://egrm.risa.gov.rw`) in a visible
browser, and `capture_flow.py` deliberately stops before the final submit so it
never creates a real grievance. New or changed screenshots need a rebuild.

The desk screenshots are in Kinyarwanda because that is the configured language
of the deployment — `?lang=` and cookies do not override it, only each user's
own `User.language`. `content/docs/glossary.mdx` carries the Kinyarwanda ↔
English label tables so the guide stays usable either way.
