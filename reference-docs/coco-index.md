Code Snippets for CocoIndex reference 

#This function converts a single PDF to Markdown:

! pip install -U cocoindex docling

'''
import pathlib

import cocoindex as coco
from cocoindex.connectors import localfs
from cocoindex.resources.file import PatternFilePathMatcher
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption

_pipeline_options = PdfPipelineOptions(
    accelerator_options=AcceleratorOptions(device=AcceleratorDevice.CPU)
)
_converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=_pipeline_options)
    }
)

@coco.fn(memo=True)
def process_file(
    file: localfs.File,
    outdir: pathlib.Path,
) -> None:
    markdown = _converter.convert(
        file.file_path.resolve()
    ).document.export_to_markdown()
    outname = file.file_path.path.stem + ".md"
    localfs.declare_file(outdir / outname, markdown, create_parent_dirs=True)
    
'''

<!-- localfs.File — A file object returned by localfs.walk_dir(), implementing the FileLike base class. See the localfs connector for full details.
memo=True — Caches results; unchanged files are skipped on re-runs
localfs.declare_file() — Declares a file target state; auto-deleted if source is removed. See localfs as target for the full API. -->

<!-- Define the main function
 -->

'''
@coco.fn
async def app_main(sourcedir: pathlib.Path, outdir: pathlib.Path) -> None:
    files = localfs.walk_dir(
        sourcedir,
        recursive=True,
        path_matcher=PatternFilePathMatcher(included_patterns=["**/*.pdf"]),
    )
    await coco.mount_each(process_file, files.items(), outdir)
'''


Use with other agents
The skill is plain Markdown — SKILL.md plus a few reference files. Any agent that accepts file-based context will work:

Cursor — copy skills/cocoindex/SKILL.md into .cursor/rules/cocoindex.md.
Generic AGENTS.md / CLAUDE.md — concatenate or @import SKILL.md from your top-level agent instructions file.
Custom RAG / agent stack — index the skills/cocoindex/ directory like any other documentation source.
s
What’s inside

kills/cocoindex/
├── SKILL.md                       # main entry — concepts, APIs, patterns
└── references/
    ├── api_reference.md           # quick API reference
    ├── connectors.md              # full connector reference
    ├── patterns.md                # detailed pipeline patterns
    ├── setup_project.md           # project setup
    └── setup_database.md          # database setup