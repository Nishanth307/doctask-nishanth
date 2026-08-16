import { useState, useRef } from "react";

interface DocumentUploadProps {
  files: File[];
  onFilesChange: (files: File[]) => void;
  disabled?: boolean;
  label?: string;
  description?: string;
  multiple?: boolean;
}

interface RejectedFile {
  name: string;
  reason: string;
}

export function DocumentUpload({
  files,
  onFilesChange,
  disabled = false,
  label = "Documents",
  description = "Drop files here",
  multiple = true,
}: DocumentUploadProps) {
  const [dragActive, setDragActive] = useState(false);
  const [rejectedFiles, setRejectedFiles] = useState<RejectedFile[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

  const validateAndAddFiles = (incomingFiles: File[]) => {
    const validFiles: File[] = multiple ? [...files] : [];
    const newRejected: RejectedFile[] = [];
    const filesToValidate = multiple ? incomingFiles : incomingFiles.slice(0, 1);

    filesToValidate.forEach((file) => {
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (ext !== "pdf" && ext !== "docx") {
        newRejected.push({
          name: file.name,
          reason: "Unsupported file type (PDF/DOCX only)",
        });
        return;
      }

      if (file.size > MAX_FILE_SIZE) {
        newRejected.push({
          name: file.name,
          reason: "File exceeds 10 MB limit",
        });
        return;
      }

      // Avoid duplicates
      const isDuplicate = validFiles.some(
        (f) => f.name === file.name && f.size === file.size
      );
      if (!isDuplicate) {
        validFiles.push(file);
      }
    });

    onFilesChange(validFiles);
    if (newRejected.length > 0) {
      setRejectedFiles((prev) => [...prev, ...newRejected]);
    }
  };

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (disabled) return;

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndAddFiles(Array.from(e.dataTransfer.files));
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndAddFiles(Array.from(e.target.files));
    }
  };

  const removeFile = (indexToRemove: number) => {
    const updated = files.filter((_, i) => i !== indexToRemove);
    onFilesChange(updated);
  };

  const removeRejected = (indexToRemove: number) => {
    setRejectedFiles((prev) => prev.filter((_, i) => i !== indexToRemove));
  };

  const onButtonClick = () => {
    inputRef.current?.click();
  };

  return (
    <div className="document-upload-container" style={{ margin: "16px 0" }}>
      <label style={{ display: "block", marginBottom: "8px", fontWeight: "bold" }}>
        {label}
      </label>

      <div
        className={`drag-drop-zone ${dragActive ? "drag-active" : ""}`}
        onDragEnter={handleDrag}
        onDragOver={handleDrag}
        onDragLeave={handleDrag}
        onDrop={handleDrop}
        onClick={onButtonClick}
        style={{
          border: dragActive ? "2px dashed #3b82f6" : "2px dashed #cbd5e1",
          borderRadius: "8px",
          padding: "32px 16px",
          textAlign: "center",
          backgroundColor: dragActive ? "#eff6ff" : "#f8fafc",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
          transition: "all 0.2s ease",
        }}
      >
        <input
          ref={inputRef}
          type="file"
          multiple={multiple}
          accept=".pdf,.docx"
          onChange={handleChange}
          disabled={disabled}
          style={{ display: "none" }}
        />
        <div style={{ color: "#475569" }}>
          <strong>{description}</strong>
        </div>
        <div style={{ color: "#64748b", fontSize: "14px", marginTop: "4px" }}>
          or click to browse
        </div>
        <div style={{ color: "#94a3b8", fontSize: "12px", marginTop: "8px" }}>
          PDF / DOCX · Max 10 MB
        </div>
      </div>

      {/* Selected Valid Files */}
      {files.length > 0 && (
        <div className="selected-files" style={{ marginTop: "16px" }}>
          <strong style={{ display: "block", marginBottom: "8px" }}>Selected files</strong>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {files.map((file, idx) => (
              <div
                key={`${file.name}-${idx}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  backgroundColor: "#f1f5f9",
                  borderRadius: "6px",
                  fontSize: "14px",
                }}
              >
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  📄 {file.name} ({(file.size / (1024 * 1024)).toFixed(2)} MB)
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeFile(idx);
                  }}
                  disabled={disabled}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#ef4444",
                    cursor: "pointer",
                    fontSize: "16px",
                    padding: "0 4px",
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rejected Files */}
      {rejectedFiles.length > 0 && (
        <div className="rejected-files" style={{ marginTop: "16px" }}>
          <strong style={{ display: "block", marginBottom: "8px", color: "#b91c1c" }}>
            Rejected files
          </strong>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {rejectedFiles.map((rejected, idx) => (
              <div
                key={`${rejected.name}-${idx}`}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "8px 12px",
                  backgroundColor: "#fef2f2",
                  border: "1px solid #fee2e2",
                  borderRadius: "6px",
                  fontSize: "14px",
                  color: "#991b1b",
                }}
              >
                <span>
                  ✕ {rejected.name} — <strong style={{ fontSize: "12px" }}>{rejected.reason}</strong>
                </span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removeRejected(idx);
                  }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#991b1b",
                    cursor: "pointer",
                    fontSize: "16px",
                    padding: "0 4px",
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
