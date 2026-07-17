import { useCallback, useEffect, useRef, useState } from "react";
import api, { formatApiErrorDetail, setAuthToken } from "../../api";
import { allLandingSectionKeys } from "../landingSectionKeys";

/**
 * @param {number|string|null} projectId
 * @param {string} token
 * @param {"draft"|"published"} view
 */
export default function useLandingTexts(projectId, token, view = "published") {
  const [byKey, setByKey] = useState({});
  const [hasUnpublishedDrafts, setHasUnpublishedDrafts] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");
  const dirtyRef = useRef({});

  const load = useCallback(async () => {
    if (!projectId || !token) return;
    setLoading(true);
    setError("");
    try {
      setAuthToken(token);
      const res = await api.get(`/projects/${projectId}/landing-texts`, {
        params: { view },
      });
      const map = {};
      for (const key of allLandingSectionKeys()) {
        map[key] = { draft_body: "", published_body: "" };
      }
      for (const t of res.data?.texts || []) {
        map[t.section_key] = {
          draft_body: t.draft_body || "",
          published_body: t.published_body || "",
          updated_at: t.updated_at,
          published_at: t.published_at,
        };
      }
      setByKey(map);
      setHasUnpublishedDrafts(!!res.data?.has_unpublished_drafts);
      dirtyRef.current = {};
    } catch (e) {
      setError(formatApiErrorDetail(e));
    } finally {
      setLoading(false);
    }
  }, [projectId, token, view]);

  useEffect(() => {
    void load();
  }, [load]);

  const setDraft = useCallback((sectionKey, value) => {
    dirtyRef.current[sectionKey] = true;
    setByKey((prev) => ({
      ...prev,
      [sectionKey]: {
        ...(prev[sectionKey] || {}),
        draft_body: value,
      },
    }));
    setHasUnpublishedDrafts(true);
    setSaveMsg("");
  }, []);

  const saveDrafts = useCallback(async () => {
    if (!projectId || !token) return false;
    setSaving(true);
    setSaveMsg("");
    setError("");
    try {
      setAuthToken(token);
      const texts = allLandingSectionKeys().map((section_key) => ({
        section_key,
        draft_body: byKey[section_key]?.draft_body ?? "",
      }));
      const res = await api.put(`/projects/${projectId}/landing-texts`, { texts });
      const map = { ...byKey };
      for (const t of res.data?.texts || []) {
        map[t.section_key] = {
          draft_body: t.draft_body || "",
          published_body: t.published_body || "",
          updated_at: t.updated_at,
          published_at: t.published_at,
        };
      }
      setByKey(map);
      setHasUnpublishedDrafts(!!res.data?.has_unpublished_drafts);
      dirtyRef.current = {};
      setSaveMsg("Borradores guardados.");
      return true;
    } catch (e) {
      setError(formatApiErrorDetail(e));
      return false;
    } finally {
      setSaving(false);
    }
  }, [projectId, token, byKey]);

  const publishDrafts = useCallback(async () => {
    if (!projectId || !token) return false;
    setSaving(true);
    setSaveMsg("");
    setError("");
    try {
      setAuthToken(token);
      // Guardar primero por si hay cambios locales
      const texts = allLandingSectionKeys().map((section_key) => ({
        section_key,
        draft_body: byKey[section_key]?.draft_body ?? "",
      }));
      await api.put(`/projects/${projectId}/landing-texts`, { texts });
      const res = await api.post(`/projects/${projectId}/landing-texts/publish`);
      const map = { ...byKey };
      for (const t of res.data?.texts || []) {
        map[t.section_key] = {
          draft_body: t.draft_body || "",
          published_body: t.published_body || "",
          updated_at: t.updated_at,
          published_at: t.published_at,
        };
      }
      setByKey(map);
      setHasUnpublishedDrafts(false);
      dirtyRef.current = {};
      setSaveMsg("Narrativa publicada. El cliente verá estos textos.");
      return true;
    } catch (e) {
      setError(formatApiErrorDetail(e));
      return false;
    } finally {
      setSaving(false);
    }
  }, [projectId, token, byKey]);

  const bodyForDisplay = useCallback(
    (sectionKey) => {
      const row = byKey[sectionKey];
      if (!row) return "";
      if (view === "draft") return row.draft_body || "";
      return row.published_body || "";
    },
    [byKey, view]
  );

  return {
    byKey,
    hasUnpublishedDrafts,
    loading,
    error,
    saving,
    saveMsg,
    load,
    setDraft,
    saveDrafts,
    publishDrafts,
    bodyForDisplay,
  };
}
