"""Evidence Graph indexing and retrieval engine with exact citation locators."""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from gxpsoft.core.crypto import compute_sha256
from gxpsoft.core.repository import repo
from gxpsoft.models.evidence import EvidenceObject


class EvidenceChunk(BaseModel):
    """Granular chunk of an EvidenceObject with precise locator metadata."""
    chunk_id: str
    evidence_id: str
    doc_title: str
    doc_type: str
    locator: str = Field(description="e.g. 'Section 4.2 (Line 22)' or 'Sensor: RTD-04B'")
    heading: str
    text: str
    source_uri: str


class EvidenceIndexer:
    """Parses, indexes, and searches controlled GxP documents and records."""

    def __init__(self) -> None:
        self.chunks: List[EvidenceChunk] = []

    def index_document_directory(self, dir_path: Path) -> int:
        """Indexes all Markdown and JSON documents in the specified directory."""
        indexed_count = 0
        for file_path in dir_path.glob("**/*.*"):
            if file_path.suffix.lower() == ".md":
                self._index_markdown_file(file_path)
                indexed_count += 1
            elif file_path.suffix.lower() == ".json":
                self._index_json_file(file_path)
                indexed_count += 1
        return indexed_count

    def _index_markdown_file(self, file_path: Path) -> EvidenceObject:
        content = file_path.read_text(encoding="utf-8")
        title_match = re.search(r"\*\*Title:\*\*\s*(.+)", content)
        doc_id_match = re.search(r"\*\*Document ID:\*\*\s*([^\n\r]+)", content)
        doc_type_match = re.search(r"#\s+(.+)", content)

        title = title_match.group(1).strip() if title_match else file_path.stem
        doc_id = doc_id_match.group(1).strip() if doc_id_match else file_path.stem
        doc_type = "SOP" if "SOP" in doc_id or "SOP" in file_path.stem else "DOCUMENT"

        evidence = EvidenceObject(
            uri=str(file_path),
            title=f"{doc_id}: {title}",
            doc_type=doc_type,
            source_system="DMS",
            raw_content=content,
            metadata={"file_name": file_path.name, "doc_id": doc_id}
        )
        repo.add_evidence(evidence)

        # Parse sections with line numbers
        lines = content.splitlines()
        current_heading = "Header"
        current_lines: List[str] = []
        start_line = 1

        for i, line in enumerate(lines, 1):
            if line.startswith("#"):
                if current_lines:
                    chunk_text = "\n".join(current_lines).strip()
                    if chunk_text:
                        self.chunks.append(
                            EvidenceChunk(
                                chunk_id=f"{evidence.evidence_id}-CHK-{len(self.chunks)+1}",
                                evidence_id=evidence.evidence_id,
                                doc_title=evidence.title,
                                doc_type=evidence.doc_type,
                                locator=f"{current_heading} (Lines {start_line}-{i-1})",
                                heading=current_heading,
                                text=chunk_text,
                                source_uri=evidence.uri,
                            )
                        )
                current_heading = line.lstrip("#").strip()
                current_lines = [line]
                start_line = i
            else:
                current_lines.append(line)

        if current_lines:
            chunk_text = "\n".join(current_lines).strip()
            if chunk_text:
                self.chunks.append(
                    EvidenceChunk(
                        chunk_id=f"{evidence.evidence_id}-CHK-{len(self.chunks)+1}",
                        evidence_id=evidence.evidence_id,
                        doc_title=evidence.title,
                        doc_type=evidence.doc_type,
                        locator=f"{current_heading} (Lines {start_line}-{len(lines)})",
                        heading=current_heading,
                        text=chunk_text,
                        source_uri=evidence.uri,
                    )
                )

        return evidence

    def _index_json_file(self, file_path: Path) -> EvidenceObject:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)

        if "equipment_id" in data:
            doc_type = "CALIBRATION_LOG"
            title = f"Equipment Calibration Log: {data.get('equipment_name', data.get('equipment_id'))}"
            source_sys = "CMMS"
        elif "batch_id" in data:
            doc_type = "BATCH_GENEALOGY"
            title = f"Batch Genealogy Record: {data.get('batch_id')} ({data.get('product_name', '')})"
            source_sys = "MES_ERP"
        elif "operators" in data:
            doc_type = "TRAINING_RECORD"
            title = "Operator Training and Qualification Matrix"
            source_sys = "LMS"
        elif isinstance(data, list) and data and "deviation_id" in data[0]:
            doc_type = "HISTORICAL_DEVIATIONS"
            title = "Historical Deviations & CAPA Register"
            source_sys = "QMS"
        else:
            doc_type = "JSON_RECORD"
            title = file_path.stem
            source_sys = "SYSTEM"

        evidence = EvidenceObject(
            uri=str(file_path),
            title=title,
            doc_type=doc_type,
            source_system=source_sys,
            raw_content=content,
            metadata={"file_name": file_path.name}
        )
        repo.add_evidence(evidence)

        # Create structured sub-chunks for precise lookup
        if doc_type == "CALIBRATION_LOG":
            for s in data.get("sensors", []):
                self.chunks.append(
                    EvidenceChunk(
                        chunk_id=f"{evidence.evidence_id}-SENS-{s.get('sensor_id')}",
                        evidence_id=evidence.evidence_id,
                        doc_title=evidence.title,
                        doc_type=evidence.doc_type,
                        locator=f"Equipment {data.get('equipment_id')} -> Sensor {s.get('sensor_id')}",
                        heading=f"Sensor {s.get('sensor_id')} ({s.get('parameter')})",
                        text=json.dumps(s, indent=2),
                        source_uri=evidence.uri
                    )
                )
        elif doc_type == "HISTORICAL_DEVIATIONS":
            for d in data:
                self.chunks.append(
                    EvidenceChunk(
                        chunk_id=f"{evidence.evidence_id}-DEV-{d.get('deviation_id')}",
                        evidence_id=evidence.evidence_id,
                        doc_title=evidence.title,
                        doc_type=evidence.doc_type,
                        locator=f"Deviation Record: {d.get('deviation_id')}",
                        heading=f"{d.get('deviation_id')}: {d.get('title')}",
                        text=json.dumps(d, indent=2),
                        source_uri=evidence.uri
                    )
                )
        else:
            self.chunks.append(
                EvidenceChunk(
                    chunk_id=f"{evidence.evidence_id}-CHK-1",
                    evidence_id=evidence.evidence_id,
                    doc_title=evidence.title,
                    doc_type=evidence.doc_type,
                    locator=f"File: {file_path.name}",
                    heading=title,
                    text=content,
                    source_uri=evidence.uri
                )
            )

        return evidence

    def search(
        self,
        query: str,
        doc_type: Optional[str] = None,
        limit: int = 5
    ) -> List[Tuple[EvidenceChunk, float]]:
        """Performs keyword and semantic relevance scoring across indexed chunks."""
        query_terms = set(re.findall(r"\w+", query.lower()))
        scored_results: List[Tuple[EvidenceChunk, float]] = []

        for chunk in self.chunks:
            if doc_type and chunk.doc_type != doc_type:
                continue

            chunk_text_lower = chunk.text.lower() + " " + chunk.heading.lower() + " " + chunk.locator.lower()
            matched_terms = sum(1 for term in query_terms if term in chunk_text_lower)
            if matched_terms > 0:
                # Score between 0.0 and 1.0
                score = round(matched_terms / max(len(query_terms), 1), 3)
                scored_results.append((chunk, score))

        scored_results.sort(key=lambda x: x[1], reverse=True)
        return scored_results[:limit]


# Global Evidence Indexer instance
evidence_indexer = EvidenceIndexer()
