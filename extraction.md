create a extraction system which can extract data from files of all formats like audio,video,pdf,docx,pptx,csv & others also for each format type we have selected the extraction tool or method which is provided below:

pdf - pymupdf
scanned pdf - paddleOCR
mixed pdf - pymupdf + paddleOCR
Image - VLM
Audio - whisper/fast whisper
video - ffmpeg+fast whisper+VLM
zip - python zipfile
csv,tsv - pandas
xlsx,xls - openpyxl + pandas
docx - python-docx
pptx - python-pptx

extraction flow is shown below:

                                  ┌─────────────────────┐
                                  │      USER UPLOAD    │
                                  │ PDF / DOCX / XLSX   │
                                  │ PPTX / IMAGE / etc. │
                                  └──────────┬──────────┘
                                             │
                                             ▼
                              ┌──────────────────────────┐
                              │    FILE INTAKE SERVICE    │
                              │                          │
                              │ • Validate file          │
                              │ • Generate document_id   │
                              │ • Calculate checksum     │
                              │ • Store original file    │
                              │ • Detect MIME type       │
                              └────────────┬─────────────┘
                                           │
                                           ▼
                              ┌──────────────────────────┐
                              │    DOCUMENT PROFILER      │
                              │                          │
                              │ • File type              │
                              │ • File metadata          │
                              │ • Page/sheet/slide count │
                              │ • Content type            │
                              │ • Text density            │
                              │ • Scan detection          │
                              │ • Tables                  │
                              │ • Images                  │
                              │ • Charts                  │
                              │ • Layout complexity       │
                              │ • Extraction strategy     │
                              └────────────┬─────────────┘
                                           │
                         ┌─────────────────┼─────────────────┐
                         │                 │                 │
                         ▼                 ▼                 ▼
                  ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
                  │    PDF      │   │   OFFICE    │   │    MEDIA    │
                  │   ROUTER    │   │   ROUTER    │   │   ROUTER    │
                  └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
                         │                 │                 │
              ┌──────────┼──────────┐      │          ┌──────┴──────┐
              │          │          │      │          │             │
              ▼          ▼          ▼      ▼          ▼             ▼
          Native      Scanned     Mixed   Office     Audio        Video
            PDF         PDF        PDF     files
              │          │          │      │          │             │
              ▼          ▼          ▼      ▼          ▼             ▼
          PyMuPDF    PaddleOCR   PyMuPDF  Native   faster-       FFmpeg
                                  + OCR    parser   whisper          │
                                                                      ├─ Audio
                                                                      │   ↓
                                                                      │ faster-whisper
                                                                      │
                                                                      └─ Frames
                                                                          ↓
                                                                         VLM
              │          │          │      │          │             │
              └──────────┴──────────┴──────┴──────────┴─────────────┘
                                             │
                                             ▼
                                  ┌────────────────────────┐
                                  │  EXTRACTION RESULTS    │
                                  │                        │
                                  │ Text                   │
                                  │ Tables                 │
                                  │ Images                 │
                                  │ Charts                 │
                                  │ Figures                │
                                  │ Metadata               │
                                  │ Coordinates            │
                                  │ Audio transcript       │
                                  │ Visual descriptions    │
                                  └────────────┬───────────┘
                                               │
                                               ▼
                                  ┌────────────────────────┐
                                  │ CANONICAL DOCUMENT     │
                                  │ REPRESENTATION          │
                                  │        (CDR)            │
                                  └───────────────────────┘