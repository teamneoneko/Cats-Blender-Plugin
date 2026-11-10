# Cats Blender Plugin

> [!IMPORTANT]
> ## 📦 CATS BLENDER PLUGIN IS NOW ARCHIVED
>
> **Version 5.3.1.0 is the final release of Cats Blender Plugin.**
>
> After twelve years, Yusarina is stepping away from VRChat and social VR, and that includes Cats. There will be no further updates, fixes or releases from NeoNeko.
>
> **Read the announcement:** [Stepping away from VRChat and social VR](https://yusarina.dev/blog/stepping-away-from-vrchat)
>
> **What does this mean?**
>
> - ✅ **This GitHub repository now holds the final Cats code**, so anyone can easily fork it and carry the project on.
> - ✅ **Cats is MIT licensed.** You are free to fork it, change it and publish your own version.
> - ✅ **The final release, the documentation and the built-in updater keep working.** NeoNeko Git stays online.
> - ❌ **No new features, fixes or releases** will be made by NeoNeko.
> - ❌ **Issues and pull requests are not accepted**, here or on NeoNeko Git. Please do not open them.
> - ❌ **No support is provided** for Cats any more.
>
> **Want Cats to keep going?** [Fork this repository](https://github.com/teamneoneko/Cats-Blender-Plugin/fork) and see [Forking Cats](#forking-cats) below.

---

## Project Links

| Resource | Link |
|---|---|
| **Source code (for forking)** | [GitHub](https://github.com/teamneoneko/Cats-Blender-Plugin) |
| **Final release / downloads** | [NeoNeko Git Releases](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/releases) |
| **Documentation / Wiki** | [NeoNeko Git Wiki](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/wiki) |
| **Original NeoNeko repository (archived)** | [NeoNeko Git](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin) |
| **Announcement** | [Stepping away from VRChat and social VR](https://yusarina.dev/blog/stepping-away-from-vrchat) |

---

## ⚠️ Support

**Cats is archived and no longer supported.** Bug reports, feature requests and support requests are not monitored or answered on GitHub or on NeoNeko Git.

If you need a fix or a new feature, the way forward is a fork. If a community fork picks Cats up, please go to that fork for support.

**Please do not ask for help with this version in the original Cats Discord server.** This NeoNeko version is an unofficial continuation and was never maintained by the original Cats developers.

---

## About Cats Blender Plugin

Cats Blender Plugin is a Blender add-on designed to simplify importing, fixing, optimizing and preparing 3D models for VRChat and other platforms.

Originally developed by Absolute Quantum and later maintained by the community, Cats provides a collection of tools that automate many otherwise time-consuming steps of avatar creation.

This unofficial continuation was maintained by **NeoNeko (Yusarina)**, focused on compatibility with modern Blender versions, performance improvements, bug fixes and new functionality.

Cats supports models and workflows from various applications and formats, including:

- MMD (MikuMikuDance)
- XNALara / XPS
- Mixamo
- Source Engine
- Unreal Engine
- DAZ / Poser
- Blender Rigify
- The Sims 2
- MotionBuilder
- Autodesk 3ds Max
- FBX
- VRM
- glTF / GLB
- And potentially more!

---

## Blender Version Support

| Blender | Cats release |
|---|---|
| **5.2 and 5.3** | **5.3.1.0** (final release) |
| **5.1** | 5.3.0.1 or earlier |
| **5.0 and older** | Older releases made for that Blender version |
| **5.4 and newer** | ❌ Not supported. Cats refuses to load; a fork is needed to add support |

All releases are on the [NeoNeko Git Releases](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/releases) page. See the [Version Support wiki page](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/wiki/Version-Support) for details.

---

## Features

### Import / Export

- Import models from MMD, XNALara/XPS, VRM, FBX, Source Engine, glTF/GLB, DAE and other supported formats.
- Export checked avatars for Unity/VRChat and Resonite.

### Model Optimization

- Combine materials and convert textures to PNG.
- Built-in **Atlas Generator**: texture atlases with optional normal, emission, roughness, metallic, AO and height maps, plus optional Cycles baking for procedural materials. No extra add-ons needed.
- Merge bones and weights, and remove zero-weight bones and vertex groups.
- Join, separate and clean up meshes.

### Eye Tracking

- Automatically configure eye tracking.
- SDK3 and legacy eye tracking workflows.

### Visemes / Lip Sync

- Automatically generate visemes for VRChat lip sync.

### Armature Tools

- Fix MMD/VRM armatures for Unity/VRChat.
- Merge armatures and attach meshes to existing rigs.
- Root bones, twist bones, digitigrade legs and Rigify conversion.

### Shape Key Tools

- Remove unused shape keys, repair broken ones and optimize static shape keys.

### Translation Tools

- Translate Japanese bone, shape key, material and object names into English.
- Internal dictionary, MMD author names, and Google, DeepL, LibreTranslate and MyMemory as online services.

### Additional Features

- Built-in avatar scaling, finger spreading and scale matching.
- UV tools.
- UI translations: English, Japanese, Korean and Simplified Chinese.

For full documentation, see the [Cats Wiki](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/wiki).

---

## Installation

> [!NOTE]
> Download the release ZIP from **[NeoNeko Git Releases](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin/releases)**. The GitHub repository holds the source code for forking; it is not a release download.

1. Download the Cats release that matches your Blender version (see [Blender Version Support](#blender-version-support)).
2. Open Blender.
3. Go to **Edit > Preferences > Get Extensions**.
4. Use the top-right drop-down menu and choose **Install from Disk**.
5. Select the downloaded Cats ZIP. **Do not extract it.**
6. Enable Cats if it was not enabled automatically.
7. In the 3D Viewport, press **N** and open the **Cats** tab.

### Requirements

- Blender from the [official Blender website](https://www.blender.org/download/) or Steam.
- **Windows Store Blender:** not supported (known permission issues).
- **Linux:** package-manager, Snap and Flatpak builds of Blender are not supported.

Material Combiner and Immersive Scaler are **no longer needed**. Cats has its own built-in atlas generator and scaler.

---

## Updating

**There will be no further updates.** 5.3.1.0 is the final release. The built-in updater still lists the existing releases on NeoNeko Git, and Blender only installs a release that supports your Blender version.

Future updates, if any, will come from community forks.

---

## Forking Cats

Cats is MIT licensed, so you are welcome to fork it and continue development. A few things to change so your fork works on its own and users can tell it apart from the archived NeoNeko version:

1. **Give it its own identity.** In `blender_manifest.toml`, change `id`, `name`, `maintainer` and `website`. A new `id` makes Blender treat your fork as a separate extension instead of clashing with an installed copy of Cats.
2. **Point the updater at your releases.** `RELEASES_API_URL` in `updater.py` points at NeoNeko Git. The updater reads `tag_name`, `zipball_url`, `body` and `published_at`, which both the Forgejo/Gitea and the GitHub releases APIs provide.
3. **Point translation downloads at your repository.** `translation_repo_api` and `dictionary_download_link` in `tools/translations.py`. Translations are fetched from a branch named after the running Blender version (for example `5.2`).
4. **Update the wiki links.** The `*.wikiURL` entries in `resources/translations/*.json` link to the NeoNeko wiki.
5. **Supporting newer Blender.** Raise `blender_version_max` in `blender_manifest.toml` and the version check in `check_unsupported_blender_versions()` in `__init__.py`, then test.
6. **Keep the versions in sync.** `CATS_VERSION` in `__init__.py` must match the `version` in `blender_manifest.toml` (a test checks this).
7. **Tests and CI.** The test suites are in `tests/` (`run_tests.py` runs them; see `tests/README.md`). CI is written for Forgejo Actions in `.forgejo/workflows/` and needs adapting for GitHub Actions. Some tests check the NeoNeko URLs and will need updating along with them.
8. **Updating MMD Tools.** MMD Tools is bundled as `mmd_tools_local`. Run `python scripts/vendor_mmd_tools.py <version>` to vendor a newer release.

Please make it clear that your fork is your own project, and don't send users to NeoNeko for support.

---

## Acknowledgements

Cats Blender Plugin was originally developed by **Absolute Quantum** and then maintained and expanded by community contributors.

This unofficial continuation was maintained by **NeoNeko (Yusarina)**. Thank you to everyone who used, tested, translated and contributed to Cats over the years, and to the wider Blender and VRChat communities.

### Code Contributors

- Hotox
- Shotariya
- Neitri
- Kiraver
- Jordo
- Ruubick
- 989onan
- rurre

### Original Cats Blender Plugin

The original Cats Blender Plugin was developed by Absolute Quantum:

[absolute-quantum/cats-blender-plugin](https://github.com/absolute-quantum/cats-blender-plugin)

**Please note:** the original Cats project and this NeoNeko continuation are separate projects.

### Third-Party Projects

Cats includes or builds on work from:

- [MMD Tools](https://github.com/MMD-Blender/blender_mmd_tools), bundled with Cats
- [Immersive Scaler](https://github.com/triazo/immersive_scaler), whose scaling tools were ported into Cats
- [Material Combiner](https://github.com/Grim-es/material-combiner-addon), which earlier versions of Cats used for atlassing

Thank you to the developers and contributors of these projects.

---

## About NeoNeko

**NeoNeko** is becoming a label for Yusarina's projects outside VR. **NeoNeko Git stays online** and remains free to use.

- **Git Hosting:** [https://git.neoneko.org](https://git.neoneko.org/)
- **Cats Blender Plugin (archived):** [NeoNeko Git](https://git.neoneko.org/NeoNeko/Cats-Blender-Plugin)

---

## License

MIT. See [LICENSE](LICENSE).](https://github.com/teamneoneko/Cats-Blender-Plugin/tree/cats-latest)
