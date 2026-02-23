# Git-Doc-Hook Examples

This directory contains example configuration files for different project types.

## Configuration Files

### `.git-doc-hook.yml`
The main configuration file with comprehensive comments explaining each option. This is the default configuration that git-doc-hook uses.

### `python-project.yml`
Configuration optimized for Python projects, including:
- Django models detection
- Flask/FastAPI route documentation
- Service layer tracking
- Test file handling

### `javascript-project.yml`
Configuration optimized for JavaScript/TypeScript projects, including:
- React component documentation
- API route tracking
- Custom hooks detection
- Package.json monitoring

## Usage

1. Copy the appropriate example to your project root:
   ```bash
   cp examples/python-project.yml .git-doc-hook.yml
   ```

2. Customize the configuration for your project:
   - Adjust file patterns in `rules`
   - Add custom document targets in `actions`
   - Configure MemOS integration in `memos`
   - Set complexity thresholds in `complexity`

3. Initialize git-doc-hook in your project:
   ```bash
   git-doc-hook init
   ```

## Key Concepts

### Rules
Rules define which files trigger documentation updates:
```yaml
rules:
  - pattern: "services/**/*.py"    # Glob pattern
    layers: ["traditional"]         # Which docs to update
    when: ["file_exists"]           # Trigger condition
    actions:                        # What to do
      - target: "README.md"
        action: "append_table_row"
```

### Layers
Layers group documentation targets:
- `traditional`: Standard docs (README, docs/)
- `config`: AI assistant config (.clinerules, .cursorrules)
- `memo`: Virtual layer for MemOS sync

### Actions
Actions define what happens when a rule matches:
- `append_table_row`: Add row to Markdown table
- `append_record`: Append content to file
- `update_section`: Replace section content
- `prepend_content`: Add content at file start

## Tips

1. **Start Simple**: Begin with basic patterns and add complexity as needed
2. **Test First**: Use `updaters.dry_run: true` to preview changes
3. **Custom Templates**: Create custom templates in `~/.git-doc-hook/templates/`
4. **Backup Enabled**: Keep `updaters.backup: true` for safety
