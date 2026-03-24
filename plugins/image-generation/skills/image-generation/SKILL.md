---
name: image-generation
description: "[Virtual] Resolves to the best available AI image generation CLI. Handles setup, provider detection, and guided install. Use when asked to generate images, create sprites, make assets, or produce artwork."
user-invocable: true
---

# Image Generation (Virtual Provider)

This is a **virtual skill** — it does not generate images itself. It resolves to the best available image generation CLI and delegates, or guides the user through installation.

## When to Activate

- User says "generate an image", "create a sprite", "make an asset", "generate artwork"
- A project's design spec references AI image generation (e.g., a DESIGN_SPEC.md for game assets)
- User wants to produce UI mockups, game assets, transparent PNGs, or marketing materials

## Resolution Protocol

### Step 1: Load Provider Registry

Read `providers.json` (in the same directory as this SKILL.md):

```bash
SKILL_DIR="$(dirname "$(find ~/.claude -path '*/image-generation/providers.json' -maxdepth 6 2>/dev/null | head -1)")"
```

### Step 2: Check Providers (in order)

For each provider in `providers.json`:

1. **nano-banana** — check if `nano-banana` command is available:
   ```bash
   nano-banana --help 2>/dev/null
   ```
   If not on PATH, check the fallback path: `~/tools/nano-banana-2/src/cli.ts`
   ```bash
   test -f ~/tools/nano-banana-2/src/cli.ts && echo "found"
   ```
   If found at fallback path but not linked, run via bun directly:
   ```bash
   bun ~/tools/nano-banana-2/src/cli.ts "<prompt>" [options]
   ```

### Step 3: Delegate or Install

**If a provider is found**: tell the user which provider is being used, then invoke it with the user's arguments.

**If no provider is found**: offer to install the recommended provider:

> No image generation CLI found. Would you like to install nano-banana?
> It uses Gemini Flash/Pro for AI image generation (~$0.067 per 1K image).
>
> 1. **Yes, install nano-banana** — needs Bun runtime + Gemini API key (free)
> 2. **No, skip** — I'll handle image generation another way

If the user picks **option 1**, walk through the install steps:

#### Install Flow

1. **Check Bun runtime**:
   ```bash
   bun --version
   ```
   If not installed, install it:
   - macOS/Linux: `curl -fsSL https://bun.sh/install | bash`
   - Windows: `powershell -c "irm bun.sh/install.ps1 | iex"`

2. **Clone and install nano-banana**:
   ```bash
   git clone https://github.com/kingbootoshi/nano-banana-2-skill.git ~/tools/nano-banana-2
   cd ~/tools/nano-banana-2 && bun install
   cd ~/tools/nano-banana-2 && bun link
   ```

3. **API key setup** — ask the user for their Gemini API key:
   ```bash
   mkdir -p ~/.nano-banana
   echo "GEMINI_API_KEY=<user's key>" > ~/.nano-banana/.env
   ```
   Get a key at: https://aistudio.google.com/apikey

4. **Verify**:
   ```bash
   nano-banana --help
   ```

### Step 4: Forward Invocation

Pass all user arguments to the resolved provider. For nano-banana:

```bash
nano-banana "<prompt>" [options]
```

Key options (see providers.json for full reference):

| Option | Description |
|--------|-------------|
| `-s, --size` | `512`, `1K`, `2K`, `4K` |
| `-a, --aspect` | `1:1`, `16:9`, `9:16`, `4:3`, etc. |
| `-m, --model` | `flash` (default, cheap) or `pro` (highest quality) |
| `-r, --ref` | Reference image for style transfer |
| `-t, --transparent` | Green screen → transparent background |
| `-o, --output` | Output filename |
| `-d, --dir` | Output directory |

## Adding a New Provider

Edit `providers.json` and add an entry to the `providers` array. See the `frontend-slides` virtual plugin for the full field reference.

The provider should support at minimum:
- Text-to-image generation from a prompt
- Output as PNG file
- Configurable output dimensions

## Why This Exists

Projects like game development need image generation but shouldn't be locked to a specific tool. This virtual skill:
- **Detects** what's already installed
- **Guides** setup when nothing is available
- **Enables swapping** — add DALL-E CLI, Stable Diffusion, or other providers to `providers.json`
- **Keeps project CLAUDE.md clean** — projects declare they need `image-generation`, not a specific tool
