# Skill Definition

---

name: skill-name
description: Brief description of the skill
Allowed-tools:

- Tool1
- Tool2

Tags:

- tag1
- tag2

---

# Skill Name

Full skill documentation in Markdown format.

## Parameters

- **param1** (type, required): Description
- **param2** (type, optional): Description

## Usage

When and how to use this skill.

## Examples

Concrete examples of skill invocation.

## Sample:

```python
skill = {
    "name": "search-web",
    "description": "Search the web for current information",
    "content": """
# search-web

Search the web for current information.

## Parameters
- **query** (string, required): Search query
- **limit** (integer, optional): Max results, default 10

## Usage
Use when the user needs current information.
"""
}
```
