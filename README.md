# Menta Linux artifacts

Holds the `.deb` packages that are published to the Menta Linux apt repository ([menta-linux/apt](https://github.com/menta-linux/apt)).

Each GitHub **release** is a **channel** (`unstable`, `testing`, `stable`, ...); its attached `.deb` files become the apt suite of the same name. Nothing is built here: packages are put in explicitly with `apt/tools/promote.sh <channel> <pkg>...`, or attached to a release by hand.

## Status page

https://menta-linux.github.io/artifacts/ lists, for every package.
