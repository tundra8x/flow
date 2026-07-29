# Flow

A gaming OS with a modern desktop.

Flow is built on [Bazzite](https://bazzite.gg) (Fedora Atomic + the Linux gaming
stack), and layers on its own desktop shell, performance tuning, and game
library. It runs real games through Proton on real hardware.

**Status: Phase 0** — build pipeline and identity. The desktop shell that makes
Flow *look* like Flow is Phase 2.

---

## How this repo works

The operating system *is* this repo. There is no hand-assembled ISO, no golden
image, no machine someone configured once and forgot. `Containerfile` plus
`build_files/build.sh` fully describe what Flow adds to its base, CI builds the
bootable image and the installer ISO, and any machine can be reproduced exactly
from a commit hash.

Two consequences worth knowing:

- **A broken build fails in CI, not on your computer.**
- **A bad update is undone by `bootc rollback` and a reboot.** You cannot brick
  a Flow machine by updating it.

## Layout

| Path | What it is |
|---|---|
| `Containerfile` | The OS. Base image + the one build step. |
| `build_files/build.sh` | Everything Flow adds: packages, branding, services. |
| `system_files/` | Files copied onto `/` verbatim. |
| `disk_config/` | Disk and ISO build config for bootc-image-builder. |
| `flow.env` | Image name, org, description. Read by the Justfile and CI. |
| `branding/` | Logo, wallpapers, boot splash (Phase 1). |
| `.github/workflows/` | Build + publish the image; build the ISO on demand. |

## Building

CI builds on every push to `main`. To build locally you need Linux with
`podman` and `just`:

```bash
just build
```

To produce an installable ISO locally:

```bash
just build-iso
```

## Installing / testing

The ISO is produced by the **Build disk images** workflow, run manually from the
Actions tab, and lands as a job artifact.

Testing in VirtualBox: **enable EFI** in the VM's settings (System → Motherboard
→ Enable EFI). Flow will not boot without it. Give it 4+ GB RAM and take a
snapshot before each test so you can revert instantly.

VirtualBox is fine for validating the shell and the look. It **cannot** validate
gaming performance — it gives a guest no usable 3D acceleration — so framerate
and latency work has to be measured on real hardware.

## Roadmap

| Phase | Delivers |
|---|---|
| 0 | Build pipeline, Flow identity — *a machine that boots and says Flow* |
| 1 | Boot splash, wallpapers, logo, Selawik font |
| 2 | **Flow Shell** — the modern desktop: taskbar, Start, window chrome, motion |
| 3 | **Performance & latency** — gamescope, GameMode, tuned profiles, benchmarks |
| 4 | **Flow Library** — add any `.exe` (or Steam/Epic) and launch it via Proton |
| 5 | Real hardware, Secure Boot, update channels |

## Known limitations

Stated plainly, because they will not change:

- **Kernel-level anti-cheat games do not run.** Valorant, most Call of Duty,
  Fortnite. This is a publisher policy decision about Linux, not a technical gap
  Flow can engineer around.
- Flow is not a Windows clone at the API level. Windows software runs through
  Proton/Wine, with Proton's compatibility characteristics.

## Licensing

The build scaffolding here is Apache-2.0 (see `LICENSE`), derived from
[ublue-os/image-template](https://github.com/ublue-os/image-template).

Flow's base image carries the licenses of its own components, including GPL
software. Redistributing Flow — free or paid — carries the obligation to offer
corresponding source for those components. Fedora trademark guidelines govern
what a rebuild may imply about Fedora. Both need to be settled before Flow is
sold; see the plan's legal section.
