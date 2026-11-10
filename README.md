# Unofficial Cats Blender Plugin

[![Static Tests](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/badges/workflows/static.yml/badge.svg?branch=main&label=Static%20Tests)](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/actions)
[![Blender 5.2 Tests](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/badges/workflows/blender-5.2.yml/badge.svg?branch=main&label=Blender%205.2%20Tests)](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/actions)
[![Latest Release](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/badges/release.svg?label=Latest%20Release)](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/releases)

## This project is archived

**5.3.1.0 is the final release of Cats.** After twelve years I'm stepping away from VRChat and social VR, and that includes Cats. There will be no further updates, and issues and pull requests are no longer being accepted.

Read more: [Stepping away from VRChat and social VR](https://yusarina.dev/blog/stepping-away-from-vrchat)

**Want to keep Cats going?** The code is on GitHub so it's easy to fork: **[github.com/teamneoneko/Cats-Blender-Plugin](https://github.com/teamneoneko/Cats-Blender-Plugin/)**. It's MIT licensed, so you're free to continue it under your own name.

The [NeoNeko Forgejo](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin) instance stays online, so the releases, the [wiki](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/wiki) and the built-in updater keep working.

Thank you to everyone who used, tested, translated and contributed to Cats.

---

Cats is a Blender add-on for importing, fixing, optimizing, and exporting avatar models, especially for VRChat-style workflows. This fork is maintained for modern Blender versions using Blender's extension package system.

The final release supports Blender 5.2 and 5.3. For Blender 5.1, use Cats 5.3.0.1 or earlier.

## Features

- Import helpers for common avatar/model formats, including MMD, XNALara/XPS, Source, FBX, VRM, and glTF/GLB workflows.
- Export helpers for checked avatar export and Resonite export.
- Armature repair tools for common imported rigs.
- Bone tools for root bones, bone merging, twist bones, digitigrade legs, and manual armature cleanup.
- Mesh cleanup tools for separating by materials, loose parts, or shapekeys.
- Shape key tools for pruning, repairing, applying shape keys to basis, and optimizing static shape keys.
- Viseme generation tools for avatar mouth shapes.
- Eye tracking setup tools for legacy and SDK3-style workflows.
- Material tools for combining duplicate materials and converting textures to PNG.
- Built-in texture atlas generator, with optional normal, emission, roughness, metallic, AO and height maps and Cycles baking.
- Translation tools for bones, shape keys, objects, and materials.
- Built-in model scaling, finger spreading and scale matching.
- Built-in updater that checks the NeoNeko Forgejo releases.
- UI translations: English, Japanese, Korean, and Simplified Chinese.

## Install

Use the release zip. Do not unzip it before installing.

1. Download the latest `.zip` from the [Releases page](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/releases).
2. Open Blender 5.2 or 5.3.
3. Go to `Edit > Preferences`.
4. Open `Get Extensions`.
5. Use the top-right drop-down menu and choose `Install from Disk`.
6. Select the downloaded Cats `.zip`.
7. Open `Add-ons`, search for `Cats`, and enable the add-on if Blender did not enable it automatically.
8. In the 3D Viewport, press `N` to open the sidebar and use the `CATS` tab.

Blender also exposes extension package installation through `Preferences > Add-ons > Install from Disk`; either path is fine as long as you select the release zip.

## Update

5.3.1.0 is the final release, so there are no further updates to install. The Cats updater panel inside Blender still lists the existing releases, and Blender only installs a release that supports your Blender version.

## Compatibility

- Blender 5.2 and 5.3: supported by the final release (5.3.1.0).
- Blender 5.1: use Cats 5.3.0.1 or earlier from the [Releases page](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/releases).
- Blender 5.0 and older: use an older release made for that Blender version.

Newer Blender versions (5.4 and later) are not supported. Cats refuses to load on them; a fork would be needed to add support.

## License

MIT. See [LICENSE](LICENSE).
