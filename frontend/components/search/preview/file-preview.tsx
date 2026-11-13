"use client";

import React from "react";
import { HybridSearchResultItem } from "@/lib/types";
import { getPreviewKind } from "./preview-utils";
import { ImagePreview } from "./image-preview";
import { VideoPreview } from "./video-preview";
import { AudioPreview } from "./audio-preview";
import { PdfPreview } from "./pdf-preview";
import { DocxPreview } from "./docx-preview";
import { TablePreview } from "./table-preview";
import { TextCodePreview } from "./text-code-preview";
import { FallbackPreview } from "./fallback-preview";

interface FilePreviewProps {
  item: HybridSearchResultItem;
}

export function FilePreview({ item }: FilePreviewProps) {
  const kind = getPreviewKind(item.file_type, item.filename, item.content_type);
  const uniqueKey = item.file_id
    ? `item-${item.file_id}-${item.chunk_index ?? 0}`
    : `item-${item.file_path}-${item.chunk_index ?? 0}`;

  switch (kind) {
    case "image":
      return (
        <ImagePreview
          key={uniqueKey}
          filePath={item.file_path}
          fileId={item.file_id}
          filename={item.filename}
          fileType={item.file_type}
        />
      );

    case "video":
      return (
        <VideoPreview
          key={uniqueKey}
          filePath={item.file_path}
          fileId={item.file_id}
          filename={item.filename}
          fileType={item.file_type}
          mediaMetadata={item.media_metadata}
        />
      );

    case "audio":
      return (
        <AudioPreview
          key={uniqueKey}
          filePath={item.file_path}
          fileId={item.file_id}
          filename={item.filename}
          fileType={item.file_type}
          mediaMetadata={item.media_metadata}
        />
      );

    case "pdf":
      return (
        <PdfPreview
          key={uniqueKey}
          filePath={item.file_path}
          fileId={item.file_id}
          filename={item.filename}
          pageNumber={item.page_number}
        />
      );

    case "docx":
      return (
        <DocxPreview
          key={uniqueKey}
          filename={item.filename}
          content={item.content}
          paragraphNumber={
            (item.metadata as Record<string, unknown> | undefined)?.paragraph_number as
              | number
              | undefined
          }
        />
      );

    case "table":
      return (
        <TablePreview
          key={uniqueKey}
          content={item.content}
          filename={item.filename}
          sheetName={item.sheet_name}
          rowNumber={item.row_number}
          fileType={item.file_type}
        />
      );

    case "code":
      return (
        <TextCodePreview
          key={uniqueKey}
          content={item.content}
          fileType={item.file_type}
          isCode
          startLine={item.start_line}
          endLine={item.end_line}
        />
      );

    case "markdown":
    case "text":
      return (
        <TextCodePreview
          key={uniqueKey}
          content={item.content}
          fileType={item.file_type}
          isCode={false}
          startLine={item.start_line}
          endLine={item.end_line}
        />
      );

    default:
      return (
        <FallbackPreview
          key={uniqueKey}
          filename={item.filename}
          filePath={item.file_path}
          fileType={item.file_type}
        />
      );
  }
}
