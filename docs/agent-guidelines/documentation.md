# Documentation Guidelines

## Principles

- Follow established ROS 2 documentation conventions.
- Keep documentation minimal, accurate, and easy to maintain.
- Document what developers need to understand or use, not what is already obvious from the code.
- Prefer concise explanations, tables, and diagrams over lengthy prose.
- Avoid duplication and unnecessary documentation.
- Treat the implementation as the source of truth.

## What to Document

Prioritize information that is important, non-obvious, or relatively stable:

- Package purpose and responsibilities.
- Public ROS 2 interfaces and expected behavior.
- Essential configuration and usage.
- Important architectural decisions and constraints.
- Non-obvious workflows, limitations, and safety considerations.

Avoid documenting:

- Internal implementation details that frequently change.
- Self-explanatory code, functions, or classes.
- Complete configuration files or parameter lists already maintained elsewhere.
- Information duplicated in other documentation.
- Speculative features or planned functionality unless explicitly requested.

Prefer linking to existing source files, configuration, or documentation rather than copying their contents.

## Package READMEs

Use the following structure when applicable:

1. Overview
2. Architecture
3. ROS 2 Interfaces
4. Configuration
5. Usage
6. Testing

Adapt the structure to the package. Omit sections that provide no meaningful information.

Keep READMEs self-contained enough to understand the package, but avoid repeating repository-level setup and deployment instructions.

## ROS 2 Interfaces

- Document public topics, services, actions, and their purpose.
- Document parameters only when necessary to understand or use the package.
- Verify interface names, types, and behavior against the implementation.
- Prefer references to configuration files over duplicating parameter defaults.
- Avoid documenting internal interfaces unless they are relevant to package integration.

## Diagrams

Use Mermaid when visualizing complex behavior is clearer than explaining it in text.

Prefer diagrams for:

- Component architecture and data flow.
- State machines and mode transitions.
- Complex sequences and interactions.
- Controller switching and distributed communication.

Keep diagrams simple and focused.

Avoid diagrams for trivial relationships or information already clear from a short explanation.

Diagrams must reflect the actual implementation.

## Examples

- Provide only essential usage examples.
- Verify commands against existing executables, launch files, and configuration.
- Prefer short, executable examples.
- Avoid duplicating examples already available in repository-level documentation.

## Maintainability

- Minimize information that must be manually synchronized with the code.
- Maintain each piece of information in one authoritative location.
- Link to existing configuration and API definitions instead of reproducing them.
- Update documentation when public behavior or interfaces change.
- Do not rewrite documentation for internal changes that do not affect its accuracy.
- Preserve useful existing documentation.

## Documentation Workflow

When documenting a ROS 2 package:

1. Inspect the implementation and existing documentation.
2. Identify missing, incorrect, or outdated information.
3. Propose only necessary documentation changes.
4. Wait for approval before modifying files.
5. Modify only the selected package's documentation.
6. Verify technical claims and links against the implementation.
7. Summarize changes and report remaining uncertainties.

Document one package at a time unless explicitly instructed otherwise.

Do not modify source code, configuration, or tests during documentation tasks. Modify changelogs only when explicitly included in the task.

## Changelogs

- Maintain a `CHANGELOG.rst` for ROS 2 packages intended for release.
- Follow established ROS changelog conventions.
- Derive changelog entries from Git history, tags, and verified changes.
- Never invent release dates, versions, or historical changes.
- Document user-visible changes, new features, bug fixes, and breaking changes.
- Omit trivial refactoring, formatting, and internal implementation details.
- Use `Forthcoming` for changes not yet included in a release.
- Keep entries concise and relevant.
- Ensure released versions match `package.xml`.
- Preserve existing release history.
- If historical changes cannot be reliably reconstructed, document only verified changes and report the uncertainty.