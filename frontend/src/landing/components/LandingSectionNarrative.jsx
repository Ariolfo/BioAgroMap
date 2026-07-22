import { useEffect, useMemo, useRef, useState } from "react";
import api, { formatApiErrorDetail, setAuthToken } from "../../api";
import { renderSimpleMarkdown } from "../simpleMarkdown";
import { fetchAuthedImageDataUrl } from "../previewUtils";

const API_IMG_SRC_RE = /src="(\/api\/[^"]+)"/g;
const IMAGE_MIME_RE = /^image\/(png|jpeg|jpg|webp|gif)$/i;

/**
 * Texto narrativo bajo una subsección.
 * - editMode: textarea markdown (admin)
 * - allowImages: botón para subir imagen / pegar (Ctrl+V) e insertar ![alt](url)
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

  const canUploadImages = Boolean(allowImages && projectId && token);
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

  const uploadImageFile = async (file) => {
    if (!file || !projectId || !token) return;
    const mime = String(file.type || "").toLowerCase();
    if (mime && !IMAGE_MIME_RE.test(mime)) {
      setUploadError("Solo se admiten PNG, JPEG, WebP o GIF.");
      return;
    }
    setUploading(true);
    setUploadError("");
    try {
      setAuthToken(token);
      const form = new FormData();
      // Clipboard puede entregar File sin nombre: forzamos extensión válida.
      let named = file;
      if (!file.name || !/\.(png|jpe?g|webp|gif)$/i.test(file.name)) {
        const mime = String(file.type || "image/png").toLowerCase();
        const ext =
          mime.includes("jpeg") || mime.includes("jpg")
            ? ".jpg"
            : mime.includes("webp")
              ? ".webp"
              : mime.includes("gif")
                ? ".gif"
                : ".png";
        named = new File([file], `imagen_pegada_${Date.now()}${ext}`, {
          type: file.type || "image/png",
        });
      }
      form.append("file", named);
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

  const onPickImage = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    await uploadImageFile(file);
  };

  const onPasteImage = async (e) => {
    if (!canUploadImages || disabled || uploading) return;
    const items = e.clipboardData?.items;
    if (!items?.length) return;
    let imageFile = null;
    for (const item of items) {
      if (item.kind === "file" && IMAGE_MIME_RE.test(item.type || "")) {
        imageFile = item.getAsFile();
        break;
      }
    }
    if (!imageFile && e.clipboardData?.files?.length) {
      const f = e.clipboardData.files[0];
      if (f && IMAGE_MIME_RE.test(f.type || "")) imageFile = f;
    }
    if (!imageFile) return;
    e.preventDefault();
    await uploadImageFile(imageFile);
  };

  if (editMode) {
    return (
      <div className="landing-narrative-editor" data-section-key={sectionKey}>
        <div className="landing-narrative-editor-head">
          <label className="landing-narrative-editor-label" htmlFor={`narr-${sectionKey}`}>
            {label}
          </label>
          {canUploadImages ? (
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
          className={`landing-narrative-textarea${canUploadImages ? " landing-narrative-textarea--tall" : ""}`}
          rows={canUploadImages ? 10 : 5}
          value={draftValue}
          disabled={disabled || uploading}
          placeholder={
            canUploadImages
              ? "Escribe texto (Markdown), sube una imagen o pégala con Ctrl+V. Ej.: **negrita**, ![foto](url)"
              : "Escribe aquí la narrativa de esta sección (Markdown: **negrita**, listas -, ## título…)"
          }
          onChange={(e) => onDraftChange?.(e.target.value)}
          onPaste={onPasteImage}
        />
        {canUploadImages ? (
          <p className="landing-narrative-hint">
            Imágenes: botón <strong>Subir imagen</strong> o pegar con <kbd>Ctrl</kbd>+<kbd>V</kbd>.
            Se insertan como Markdown <code>![alt](url)</code> y se ven al publicar.
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
