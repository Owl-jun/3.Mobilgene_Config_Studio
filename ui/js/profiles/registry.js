/**
 * Profile registry — maps profile id to view renderer.
 * Extend here when adding P1+ CRUD editors.
 */

const PROFILE_META = {
  gateway: {
    label: "Gateway",
    views: ["matrix", "tree"],
    defaultView: "matrix",
    matrixLabel: "매핑 테이블",
    treeHint: "원본 XML — 가독성은 매핑 테이블 탭 권장",
  },
  ecuc: {
    label: "ECUC",
    views: ["containers", "tree"],
    defaultView: "containers",
  },
  swc_app: { label: "App SWC", views: ["tree"], defaultView: "tree" },
  swc_bsw: { label: "BSW SWC", views: ["tree"], defaultView: "tree" },
  dbc_cluster: { label: "DBC Cluster", views: ["tree"], defaultView: "tree" },
  generic: { label: "Generic", views: ["tree"], defaultView: "tree" },
};

export function getProfileMeta(profileId) {
  return (
    PROFILE_META[profileId] || {
      label: profileId,
      views: ["tree"],
      defaultView: "tree",
    }
  );
}

export function profileBadge(profileId) {
  const m = getProfileMeta(profileId);
  return m.label;
}
