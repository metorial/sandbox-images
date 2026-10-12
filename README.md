# Sandbox Images

Generic base images for Metorial's global/shared sandbox templates. Every template
is a top-level directory containing `manifest.json` and a self-contained
`build/Dockerfile`. Images target **linux/arm64**, matching Genesis machine images.

| Family | Tracks | Upstream base |
| --- | --- | --- |
| Ubuntu | 22.04, 24.04, 26.04 | Ubuntu LTS |
| Debian | 12, 13 | Debian slim |
| Node.js | 22, 24, 26 | Node.js on Debian Bookworm slim |
| Bun | 1.2, 1.3, 1.4 | Oven's Debian images |
| Python | 3.11, 3.12, 3.13, 3.14 | Python on Debian Bookworm slim |
| Go | 1.26, 1.27 | Go on Debian Bookworm |
| Development Base | Node 24 + Python 3.13 + Bun 1.3 | Python + official Node/Bun binaries |
| Python Data | Python 3.13 | Python with NumPy, pandas, SciPy, matplotlib, seaborn, Polars, DuckDB, PyArrow |
| Browser Node | Node 24 + Playwright 1.64.0 | Node with Chromium and browser dependencies |
| Browser Python | Python 3.13 + Playwright 1.63.0 | Python with Chromium and browser dependencies |
| Rust | 1 | Rust with Cargo, rustfmt, Clippy, OpenSSL development headers |
| Java | 21, 25 | Eclipse Temurin with Maven and Gradle 9.1.0 |
| .NET | 10 | Microsoft .NET SDK on Ubuntu Noble |
| Ruby | 3.4, 4.0 | Ruby with Bundler and native-extension headers |
| PHP | 8.4, 8.5 | PHP CLI with Composer, intl, mbstring, PDO, zip and OPcache |
| Deno | 2.9.7 | Official Deno Debian image |
| Documents | Python 3.13 | Office/PDF libraries, LibreOffice, Poppler, Tesseract, fonts |
| Media | Python 3.13 | FFmpeg, ImageMagick, Pillow, OpenCV |
| Alpine | 3.23, 3.24 | Alpine with musl and native build tools |

There are 34 templates across 19 families. Upstream version tags generally float within their track, so rebuilding picks up new patch
releases and OS packages. Older tracks provide compatibility; upstream support
lifetimes still apply. All images include Bash, CA certificates, curl, Git, SSH,
C/C++ build tools, procps, and unzip. They run as root in `/workspace`, clear
upstream application entrypoints, and default to `sleep infinity` for sandbox use.
Python images include pip; Node.js includes npm; Bun and Go include their own
package tooling. Isolation is provided by the sandbox runtime.

The development image also provides pnpm, TypeScript, uv/uvx, jq, ripgrep, SQLite,
and OpenSSL/pkg-config headers. Specialized images have pinned Python dependency
sets (including transitive dependencies) in `build/requirements.txt`; their source
lists are `requirements.in`. The Node browser image uses `npm ci` with a committed
lockfile. uv is pinned to 0.10.0. Node Playwright is pinned to 1.64.0 and Python
Playwright to 1.63.0 (their published release versions differ), each with its
matching Chromium build. Deno and Gradle use explicit release tags. Update these pins
intentionally to pick up tool/library releases; scheduled builds continue to pick
up updates from floating OS/language base tags and package repositories.

Browser images provide headless Chromium, without a desktop. The Node image's
Playwright module is installed in `/opt/browser/node_modules`, exposed through
`NODE_PATH`; use `require('playwright')`, or add matching Playwright 1.64.0 to your
project for ESM imports. `PLAYWRIGHT_BROWSERS_PATH=/opt/playwright` is set in both
browser images. Each smoke test launches Chromium, renders HTML and writes a
screenshot. The document smoke test converts a DOCX to PDF through LibreOffice
and parses the resulting PDF. The media smoke test reads an image through OpenCV
and encodes a short video through FFmpeg.

Alpine uses `apk` and musl; the other templates use Debian/Ubuntu and glibc. Native
binaries and Python wheels built for glibc need an Alpine-compatible build to run
there.

## Manifests and releases

`schemaVersion` versions the manifest format. `runtimeVersion` identifies the
upstream track. `version` is a per-template integer release counter, independent
of the language version. `version: 0`, `image: null`, and `digest: null` mean that
the template has not yet been published. The first successful publication sets
version 1. Each different output digest increments the counter once; identical
output leaves the manifest byte-for-byte unchanged.

Published manifests record a digest-pinned OCI image reference, for example:

```json
{
  "version": 1,
  "image": "ghcr.io/metorial/sandbox-images/node-24@sha256:…",
  "digest": "sha256:…"
}
```

Each release also has a `v1`, `v2`, etc. tag in its template's GHCR package. Use the
manifest's digest reference to consume the exact build. Published release tags
are retained; this repository does not garbage-collect previous versions.

These manifests are this repository's catalog contract. A product importer can
read the manifest version and upload each `build/` directory through Genesis's
`globalMachineImage.build.create` context-upload flow. The workflow publishes OCI
images and an HTTP discovery catalog; registering templates in a deployed Genesis
instance remains a separate integration and requires that instance's credentials.

## Scheduled builds

`.github/workflows/build-images.yml` runs daily at **03:00 and 15:00 UTC**, on
manual dispatch, and on changes to templates/build tooling on `main`. GitHub may
delay scheduled jobs. Pull requests build and smoke-test the whole catalog without
publishing or editing manifests. Publishing runs only on the default branch.

The workflow:

1. Validates every manifest and tests the version-update logic.
2. Builds every template with fresh base images and package indexes (`--pull`,
   `--no-cache`) on a native ARM64 runner. The dedicated CI builder cache is
   pruned after each build to bound disk usage while retaining release archives.
3. Smoke-tests each language runtime and the shared tools.
4. Compares the OCI output digest against the committed manifest.
5. After **all builds and tests pass**, copies changed OCI archives to GHCR with
   their digests preserved, then updates the corresponding manifests.
6. Packs all manifests and build contexts, retains older releases, and deploys the
   discovery catalog to Cloudflare Pages.
7. Commits and pushes only changed manifests with `GITHUB_TOKEN`. Bot token pushes
   do not trigger another workflow run.

BuildKit receives a fixed `SOURCE_DATE_EPOCH=0` and rewrites layer timestamps.
Dockerfiles remove package indexes, logs, temporary files, and ldconfig's
auxiliary cache (which embeds build-specific inode numbers). Provenance and SBOM
attestations are disabled for these digest comparisons because build metadata can
change independently of the runtime image. Actual changes to image configuration,
files, or base layers create a new release. Future Dockerfile additions must also
avoid random or time-dependent file contents.

Publishing workflows are serialized. If a build, smoke test, or registry copy
fails, no manifest updates are written. A failed Git push fails the job; rerun
from the current branch to publish and record its images. Some registry uploads
can already exist after a failure, but committed manifests keep pointing at the
previous successful catalog.

## New upstream version discovery

`discover-versions.yml` checks for missing tracks twice daily at **01:30 and
13:30 UTC**, and on manual dispatch. `scripts/version-sources.json` defines
upstream sources, stable tag patterns, seed templates and base-image replacements.
Docker Official Images' maintained source files provide ARM64-capable stable tags;
Bun and Deno use Docker Hub's tag API, and .NET uses Microsoft's registry tag list.

The check covers Ubuntu LTS, Debian, Node, Bun, Python, Go, Rust, Java LTS, Ruby,
PHP, Alpine, Deno and .NET. It adds newer tracks than each configured seed; it
keeps existing tracks and does not backfill older releases. Prerelease/RC/canary
tags are excluded. Upstream APIs must all succeed before files are generated.
New directories copy the family's seed build context, replace the final base
image, and start at version 0 with no published image or digest.

The action builds and smoke-tests every newly discovered image on ARM64 before
opening or updating a single PR on `codex/new-sandbox-versions`. Nothing is
published until that PR is merged and the publishing workflow runs. These tests
run directly in the discovery job because PRs created with `GITHUB_TOKEN` do not
trigger ordinary PR workflows. Enable **Allow GitHub Actions to create and
approve pull requests** in repository Actions settings. The workflow requests
`contents: write` and `pull-requests: write` and needs no custom secret.

Specialized image dependency pins, browser versions, the combined development
image, and supporting tools such as Gradle/uv are maintained separately; new
language tracks are cloned from a working seed and must pass builds before the
PR is created. A base distro/tag-layout change requires updating the source
configuration. Deno is tracked by major version; its initial image is pinned to
the newest stable Debian release available for that new major.

```sh
python3 scripts/discover_versions.py
python3 scripts/discover_versions.py --write --output /tmp/new-templates.json
```

## GitHub setup

Push this repository to `metorial/sandbox-images`, enable Actions, and run
**Build Sandbox Images** once to publish version 1. Scheduled workflows run from
the default branch. No custom secrets are required: the workflow uses
`GITHUB_TOKEN` with `contents: write` and `packages: write`.

Repository/org policies must allow the Actions bot to push manifest commits to
the default branch and create GHCR packages. If branch rules require pull requests,
configure a bot exception or adapt the final commit step to open a pull request.
Existing GHCR packages must grant this repository Actions write access. GHCR
package visibility is configured separately: make packages public for anonymous
consumers, or configure registry credentials for private consumers.

## Local checks

Requires Python 3.9+, Docker, and Buildx with a `docker-container` builder
(BuildKit 0.13+ and Buildx 0.13+ for multiple exporters and timestamp rewriting).

```sh
python3 scripts/build.py --validate
python3 -m unittest discover -s tests -v

docker buildx create --name sandbox-images --driver docker-container
BUILDX_BUILDER=sandbox-images python3 scripts/build.py --template node-24
BUILDX_BUILDER=sandbox-images python3 scripts/build.py
```

Local builds smoke-test images and report prospective updates, leaving manifests
untouched. Run on ARM64, or install ARM64 emulation on an x86 Docker host. Temporary
OCI archives and smoke-test Docker images are removed after successful checks;
BuildKit caches remain in the selected builder.

Publishing additionally requires `skopeo` and a GHCR login in Docker's config:

```sh
docker login ghcr.io
BUILDX_BUILDER=sandbox-images python3 scripts/build.py --publish
```

Pass `--authfile PATH` if using a separate registry auth file. Credential-helper
Docker logins may require a Skopeo-compatible auth file. `--registry` changes the
registry prefix for unpublished templates; published catalogs need an explicit
migration. `--publish` always builds the whole catalog.

## Add a template

Create `<id>/build/Dockerfile` and `<id>/manifest.json`, copying a related template.
Set `id` to the directory name, update name/description/runtime/runtimeVersion and
`smokeTest`, and start with version 0 and null image/digest. The build context is
only that template's `build/` directory. Keep it self-contained, use an explicit
upstream version track, and clear inherited entrypoints. Discovery is automatic;
no workflow matrix or image list needs editing. Keep published version/image/digest
fields managed by the build script.

Reproducible export behavior follows the [Docker BuildKit documentation](https://github.com/moby/buildkit/blob/master/docs/build-repro.md).

## Genesis discovery catalog

The production discovery endpoint is `https://sandbox-images.metorial.net/index.json`.
The build workflow publishes it after every successful production build, including
runs with no image changes. The Cloudflare Pages project `sandbox-images` is a
direct-upload project in the Metorial account, with the custom domain
`sandbox-images.metorial.net` and a proxied CNAME to `sandbox-images.pages.dev`. GitHub has a `CLOUDFLARE_API_TOKEN`
secret scoped to Pages Write for this account and a `CLOUDFLARE_ACCOUNT_ID`
repository variable that the workflow uses for deployment.
Wrangler is pinned to 4.149.0. Pull requests only validate packaging and never deploy.

`index.json` uses `schemaVersion: 1` and a `templates` array. Each entry includes
`id`, `name`, integer `version`, `platform`, `runtime`, `runtimeVersion`, `published`,
and two asset descriptors:

- `manifest`: `url`, `bytes`, and hex `sha256`, pointing to the template manifest.
- `build`: `url`, `bytes`, and hex `sha256`, plus `format: "tar_gzip"`,
  `dockerfilePath: "Dockerfile"`, `contextPath: "."`, and
  `buildArgs: {"SOURCE_DATE_EPOCH": "0"}`.

Build tarballs contain the source build context, with Dockerfile at the archive
root. They do not contain OCI image layers. The manifest's digest-pinned `image`
field identifies the exact tested OCI image in GHCR. Rebuilding the source context
in Genesis can pick up newer floating base tags and packages; consumers requiring
the exact tested filesystem should use the manifest's pinned OCI image.

A Genesis importer can read the index, skip entries with `published: false`, compare
manifest versions and image digests, verify each downloaded asset's size and SHA-256,
then submit the context using `globalMachineImage.build.create` and its upload URL.
This repository publishes the discovery contract; the current Genesis code does not
include an HTTP catalog importer. It must not pass the public archive URL directly
as an API input: Genesis currently issues its own context upload URL.

Asset URLs include the image version and a hash covering both manifest and context.
They are immutable even if source metadata changes without changing image output.
`releases.json` records all previous releases; packing downloads and verifies their
assets so later Pages deployments preserve old download URLs. Missing inventory
(HTTP 404) initializes a new catalog. Other download or checksum failures abort
publication. The mutable index is served with `Cache-Control: no-cache`; release
assets have a one-year immutable cache policy. Assets are limited to 25 MiB and the
site to 20,000 files. Exceeding either limit fails packaging.

Production packing rejects unpublished templates. To inspect the complete source
catalog before its first image build, use preview mode:

```sh
python3 scripts/pack.py --output /tmp/sandbox-catalog \
  --base-url https://catalog-preview.sandbox-images.pages.dev --allow-unpublished
wrangler pages deploy /tmp/sandbox-catalog --project-name sandbox-images \
  --branch catalog-preview
```

Production command (use an empty output directory):

```sh
python3 scripts/pack.py --base-url https://sandbox-images.metorial.net --retain-releases
wrangler pages deploy dist --project-name sandbox-images --branch main
```

A Pages failure prevents the manifest commit. Registry uploads may already exist,
but the last committed versions remain unchanged. Retry the build workflow from
the current default branch. An initial catalog preview is available on
`https://catalog-preview.sandbox-images.pages.dev/index.json`; version-zero entries
are explicitly marked unpublished and are not production releases.
