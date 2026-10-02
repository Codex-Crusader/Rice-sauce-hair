# Rice-sauce-hair

> Say it fast and it sounds like "Chrysos Heir". Read it slowly and it is rice, with sauce, and a hair in it.
> That is a correct description of this rice.

![The desktop](assets/showcase.gif)

A Hyprland desktop for Arch Linux, themed on Amphoreus from Honkai: Star Rail.
It has desktop widgets, falling golden leaves, and a local AI companion that can open apps,
control Chrome tabs, and run commands.

## Warning: it is very glitchy

- It was made for one laptop. It was tested on that laptop only.
- Expect broken parts on your machine. Some fixes need you to read and change the code.
- Back up your configs before you install. The installer saves files that it replaces, but be careful.
- Read [Known issues](docs/KNOWN-ISSUES.md) first.

## Not included

You must add these yourself. The guide is in [Customize](docs/CUSTOMIZE.md).

| Part | What you get |
|---|---|
| Wallpaper | A black screen |
| Companion persona and sprite sheet | A shape that says "sprite sheet shows up here" |
| Chrysos Heir card artwork | A card that says "artwork here" |

## Install

```sh
git clone --recurse-submodules https://github.com/Codex-Crusader/Rice-sauce-hair ~/dotfiles
~/dotfiles/install.sh
```

The installer only makes links. Packages, the AI model, and the login screen are manual steps:
read the full [Install guide](docs/INSTALL.md).

## Documents

- [Install guide](docs/INSTALL.md): packages, links, first start, optional parts.
- [Customize](docs/CUSTOMIZE.md): wallpaper, sprites, cards, colors, keys, widgets.
- [The companion](docs/COMPANION.md): how the AI works, its tools, and its safety rules.
- [Known issues](docs/KNOWN-ISSUES.md): what is broken or fragile.
- [Recovery](docs/RECOVERY.md): what to do when something fails.

## About this repo

- This is a hobby project. I do not sell it, and I get no money from it.
  I made this public copy because a friend asked for it.
- I keep a private repo with my full personal setup, for my own maintenance.
  If you want to ask about those specific parts, open an issue.
- Not affiliated with HoYoverse. Honkai: Star Rail, Amphoreus, and its characters belong to HoYoverse.
- Included third-party parts: the Cinzel font (SIL Open Font License, `fonts/cinzel/OFL.txt`) and
  [fzf-tab](https://github.com/Aloxaf/fzf-tab) (git submodule).
