import { useEffect, useMemo, useRef, useState } from "react";
import api, { formatApiErrorDetail, setAuthToken } from "../../api";
import { renderSimpleMarkdown } from "../simpleMarkdown";
import { fetchAuthedImageDataUrl } from "../previewUtils";

const API_IMG_SRC_RE = /src="(\/api\/[^"]+)"/g;

/**
 * Texto narrativo bajo una subsección.
 * - editMode: textarea markdown (admin)
 * - allowImages: botón para subir imagen e insertar ![alt](url)
 * - read: render markdown; si vacío no muestra nada
 */
export default function LandingSectionNarrative({
  sectionKey,
  editMode = false,
  draftValue = "",
  onDraftChange,
  displayBody = "",
  disabled = false,
  allowImages = false,
  projectId = null,
  token = "",
  label = "Texto explicativo (Markdown)",
}) {
  const fileRef = useRef(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  /** src /api/... → data-URL (imágenes protegidas por JWT). */
  const [resolvedImgs, setResolvedImgs] = useState({});

  const rawHtml = useMemo(
    () => (editMode ? "" : renderSimpleMarkdown(displayBody)),
    [editMode, displayBody]
  );

  useEffect(() => {
    if (editMode || !rawHtml) return undefined;
    const srcs = [...rawHtml.matchAll(API_IMG_SRC_RE)].map((m) => m[1]);
    const pending = [...new Set(srcs)].filter((s) => !resolvedImgs[s]);
    if (!pending.length) return undefined;
    let cancelled = false;
    (async () => {
      for (const src of pending) {
        try {
          const dataUrl = await fetchAuthedImageDataUrl(src, token);
          if (cancelled) return;
          setResolvedImgs((prev) => (prev[src] ? prev : { ...prev, [src]: dataUrl }));
        } catch {
          /* imagen no disponible: se deja el src original */
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editMode, rawHtml, token]);

  const insertAtCursor = (snippet) => {
    const el = document.getElementById(`narr-${sectionKey}`);
    const current = String(draftValue || "");
    if (!el || typeof el.selectionStart !== "number") {
      onDraftChange?.(current ? `${current.trimEnd()}\n\n${snippet}\n` : `${snippet}\n`);
      return;
    }
    const start = el.selectionStart;
    const end = el.selectionEnd;
    const next = `${current.slice(0, start)}${snippet}${current.slice(end)}`;
    onDraftChange?.(next);
    requestAnimationFrame(() => {
      el.focus();
      const pos = start + snippet.length;
      el.setSelectionRange(pos, pos);
    });
  };

  const onPickImage = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !projectId || !token) return;
    setUploading(true);
    setUploadError("");
    try {
      setAuthToken(token);
      const form = new FormData();
      form.append("file", file);
      const res = await api.post(`/projects/${projectId}/landing-media`, form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      const md = res.data?.markdown || `![imagen](${res.data?.url || ""})`;
      insertAtCursor(`\n${md}\n`);
    } catch (err) {
      setUploadError(formatApiErrorDetail(err));
    } finally {
      setUploading(false);
    }
  };

  if (editMode) {
    return (
      <div className="landing-narrative-editor" data-section-key={sectionKey}>
        <div className="landing-narrative-editor-head">
          <label className="landing-narrative-editor-label" htmlFor={`narr-${sectionKey}`}>
            {label}
          </label>
          {allowImages ? (
            <div className="landing-narrative-editor-actions">
              <button
                type="button"
                className="landing-narrative-upload-btn"
                disabled={disabled || uploading || !projectId}
                onClick={() => fileRef.current?.click()}
              >
                {uploading ? "Subiendo…" : "Subir imagen"}
              </button>
              <input
                ref={fileRef}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif"
                hidden
                onChange={onPickImage}
              />
            </div>
          ) : null}
        </div>
        <textarea
          id={`narr-${sectionKey}`}
          className={`landing-narrative-textarea${allowImages ? " landing-narrative-textarea--tall" : ""}`}
          rows={allowImages ? 10 : 5}
          value={draftValue}
          disabled={disabled || uploading}
          placeholder={
            allowImages
              ? "Escribe texto (Markdown) y/o sube imágenes. Ej.: **negrita**, listas -, ## título, ![foto](url)"
              : "Escribe aquí la narrativa de esta sección (Markdown: **negrita**, listas -, ## título…)"
          }
          onChange={(e) => onDraftChange?.(e.target.value)}
        />
        {allowImages ? (
          <p className="landing-narrative-hint">
            Las imágenes se insertan como Markdown <code>![alt](url)</code> y se muestran al publicar.
          </p>
        ) : null}
        {uploadError ? <p className="landing-narrative-error">{uploadError}</p> : null}
      </div>
    );
  }

  if (!rawHtml) return null;

  const html = rawHtml.replace(API_IMG_SRC_RE, (full, src) =>
    resolvedImgs[src] ? `src="${resolvedImgs[src]}"` : full
  );

  return (
    <div
      className="landing-narrative-box"
      data-section-key={sectionKey}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
