## Tasks

### Obsidian

- init vault: `poe vault:init`
  - calls `srcx vault-init .agents/<project or directory name>`
- cp file to vault: `poe vault:cp [-d/--vault-dir=inbox] path/to/file`
  - copies the file into the obsidian vault at `.agents/<project or directory name>`
- open file in Obsidian:
  - restrict to .md files
  - run cp task
  - use Obsidian CLI to open the file

### Editing

- easier file editing: `poe edit -p/--package <package name, eg stitch-tasks> <file>`
  - file can be partial
  - search to find the most likely candidate (searching can probably be a common utility)
  - open the file in $EDITOR
