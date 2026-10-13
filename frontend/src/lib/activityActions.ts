export type ActionGroup = {
  label: string;
  actions: string[];
};

/** Grouped actions for the Activity filter popover (server action strings). */
export const ACTIVITY_ACTION_GROUPS: ActionGroup[] = [
  {
    label: "Users",
    actions: ["member_role_changed", "membership_deactivated", "user_deactivated"],
  },
  {
    label: "Invitations",
    actions: ["user_invited", "member_invited", "invitation_accepted", "invitation_revoked", "invitation_resent"],
  },
  {
    label: "Organization",
    actions: ["organization_created", "organization_license_updated", "provisioning_job_created", "provisioning_job_retried"],
  },
  {
    label: "Sources",
    actions: ["source_connected"],
  },
  {
    label: "Settings",
    actions: [
      "client_document_uploaded",
      "client_document_removed",
      "model_token_configured",
      "model_token_tested",
      "employee_link_copied",
    ],
  },
  {
    label: "Security",
    actions: [
      "answer_approved",
      "answer_edited",
      "stale_answer_approved",
      "stale_answer_revalidated",
      "questionnaire_created",
      "questionnaire_uploaded",
      "questionnaire_exported",
      "answer_library_upserted",
      "answer_reused_from_library",
      "answer_marked_stale",
      "evidence_changed",
    ],
  },
];

export const ALL_ACTIVITY_ACTIONS = ACTIVITY_ACTION_GROUPS.flatMap((g) => g.actions);
