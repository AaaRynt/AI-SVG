# AI-SVG

Experiments on generating complex SVG artwork with AI coding agents.

This repository records a series of attempts to let AI generate large-scale, standalone SVG files using code.

The goal was not only to create images, but to explore a more interesting question:

> How far can current AI systems go when transforming descriptions into structured vector graphics?

The experiments focus on SVG because it sits between programming and visual design:

- Unlike raster image generation, SVG requires explicit structure.
- Every curve, path, layer, and label must exist as code.
- The result is inspectable, editable, and reproducible.

However, this also exposes the limitations of current AI systems.

A model can generate thousands of lines of valid SVG code, but creating a visually convincing and professionally designed graphic requires much more than producing code that runs.

## Experiments

### 1. Realistic Mount Fuji SVG

**Objective**

Generate a detailed vector illustration of Mount Fuji containing:

- mountain silhouette
- snow layers
- clouds
- sunrise lighting
- city skyline
- forest foreground
- atmospheric perspective

**Result**

The final SVG contains thousands of vector elements and can be rendered independently without external images or resources.

The result demonstrates that AI is already capable of producing complex layered vector artwork.

However, the output is closer to a vector illustration than a physically realistic landscape.

The model can create many visual details, but maintaining natural composition, lighting consistency, and artistic judgment remains difficult.

### 2. Fictional Metro Network Map

**Objective**

Generate a complete fictional metropolitan railway map.

Requirements included:

- large-city scale network
- bilingual station labels
- airports
- railway hubs
- rivers and geographic regions
- multiple metro lines
- transfer stations
- structured network data
- SVG generation and validation pipeline

**Result**

The AI successfully created:

- a fictional city plan
- structured railway data
- a complete SVG map
- automatic validation scripts

The engineering workflow was successful.

However, the visual result exposed a major limitation:

Generating a valid network is much easier than designing a readable transit map.

The AI was able to satisfy numerical requirements:

- number of lines
- number of stations
- transfer relationships
- file validity

But it struggled with:

- global layout optimization
- line organization
- visual hierarchy
- typography
- information density
- professional cartographic design

A map can be technically correct while still being difficult for humans to use.

## Observations

During these experiments, several patterns became clear.

### Code generation is not the same as design

AI can generate thousands of lines of SVG code and create complex structures.

However, visual design contains many implicit rules:

- balance
- hierarchy
- rhythm
- readability
- user perception

These rules are difficult to describe completely as constraints.

### Automated validation has limitations

A file can pass checks such as:

- valid XML
- valid SVG structure
- no missing references
- no detected collisions

while still looking wrong to humans.

For example:

- labels may technically not overlap but remain unreadable
- a metro network may be connected but visually chaotic
- an illustration may contain many details but lack realism

Passing tests does not always mean achieving the intended quality.

### Current AI is strong at expansion, weaker at refinement

The models are very good at:

- generating large amounts of content
- creating structured data
- writing supporting scripts
- building complete workflows

They are weaker at:

- deciding what details should be removed
- maintaining visual simplicity
- evaluating their own output critically
- matching professional human-made design standards

## Project Status

This repository is archived.

The experiments are considered complete.

The purpose of this repository is not to provide production-quality SVG artwork, but to preserve observations about the current capabilities and limitations of AI-assisted creation.

Future models may improve significantly in visual reasoning and SVG generation. Keeping these early experiments provides a baseline for comparison.

## Structure

```text
.
├── README.md
└── runs
    ├── fuji
    │   ├── AGENTS.md
    │   ├── metadata.json
    │   ├── *.svg
    │   └── validation files
    │
    └── metro
        ├── AGENTS.md
        ├── metadata.json
        ├── network.json
        ├── *.svg
        └── validation files
```

## Final Thoughts

This project started from a simple idea:

Can an AI create a complex SVG image purely through code?

The answer is yes.

But the more interesting discovery was that generating complexity is not the hardest part.

The difficult part is knowing what complexity is meaningful.

A future AI system may generate SVGs with better artistic judgment, stronger spatial reasoning, and deeper understanding of human visual communication.

This repository is a snapshot of the point before that future arrives.
