import { useState, useEffect, useCallback, useRef } from "react";
import {
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  Copy,
  Loader2,
  AlertCircle,
  MapPin,
  ChevronDown,
} from "lucide-react";
import { useTranslate } from "@/hooks/useTranslate";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Project {
  name: string;
  title: string;
  project_code: string;
}

interface OptionItem {
  name: string;
  category_name?: string;
  issue_type_name?: string;
}

interface AdminLevel {
  name: string;
  level_name: string;
  level_order: number;
}

interface RegionOption {
  name: string;
  region_name: string;
  administrative_level: string;
}

interface SubmissionConfig {
  otp_enabled: boolean;
  turnstile_site_key: string | null;
}

interface FormData {
  project: string;
  category: string;
  issueType: string;
  region: string;
  issueDate: string;
  description: string;
  contactMedium: "anonymous" | "updates";
  phone: string;
  otp: string;
  contactInfoType: string;
  contactInformation: string;
  citizenName: string;
  gender: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiCall<T = any>(method: string, params?: Record<string, any>): Promise<T> {
  const url = `/api/method/egrm.api.public_submit.${method}`;
  const isGet = !["send_otp", "submit_grievance"].includes(method);

  if (isGet) {
    const qs = params
      ? "?" +
        Object.entries(params)
          .filter(([, v]) => v != null && v !== "")
          .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
          .join("&")
      : "";
    const res = await fetch(url + qs);
    const data = await res.json();
    return data.message;
  }

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Frappe-CSRF-Token": (window as any).csrf_token || "",
    },
    body: JSON.stringify(params),
  });
  const data = await res.json();
  return data.message;
}

// ---------------------------------------------------------------------------
// Turnstile widget
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    turnstile?: {
      render: (el: string | HTMLElement, opts: any) => string;
      reset: (id: string) => void;
      remove: (id: string) => void;
    };
  }
}

function TurnstileWidget({
  siteKey,
  onToken,
}: {
  siteKey: string;
  onToken: (token: string) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);

  useEffect(() => {
    if (!containerRef.current || !window.turnstile) return;
    if (widgetIdRef.current) {
      try {
        window.turnstile.remove(widgetIdRef.current);
      } catch {}
    }
    widgetIdRef.current = window.turnstile.render(containerRef.current, {
      sitekey: siteKey,
      callback: onToken,
      "refresh-expired": "auto",
    });

    return () => {
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {}
      }
    };
  }, [siteKey, onToken]);

  return <div ref={containerRef} className="flex justify-center my-4" />;
}

// ---------------------------------------------------------------------------
// Progress Dots
// ---------------------------------------------------------------------------

function ProgressDots({ current, total }: { current: number; total: number }) {
  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      {Array.from({ length: total }, (_, i) => {
        const step = i + 1;
        const isActive = step === current;
        const isDone = step < current;
        return (
          <div
            key={step}
            className={`w-2.5 h-2.5 rounded-full transition-all ${
              isActive
                ? "bg-primary-500 scale-125"
                : isDone
                  ? "bg-primary-400"
                  : "bg-gray-300"
            }`}
          />
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cascading Region Selector
// ---------------------------------------------------------------------------

function CascadingRegionSelector({
  project,
  adminLevels,
  value,
  onChange,
  __,
}: {
  project: string;
  adminLevels: AdminLevel[];
  value: string;
  onChange: (regionName: string) => void;
  __: (s: string) => string;
}) {
  // Each level holds: { selected region name, options[] }
  const [levels, setLevels] = useState<
    { level: AdminLevel; options: RegionOption[]; selected: string; loading: boolean }[]
  >([]);

  // Load first level on mount / project change
  useEffect(() => {
    if (!project || adminLevels.length === 0) {
      setLevels([]);
      return;
    }
    loadChildren(null, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, adminLevels]);

  const loadChildren = async (parentRegion: string | null, levelIdx: number) => {
    // Find which admin level this corresponds to
    // The API returns children - their admin_level tells us which level they are
    // We start from the first visible level (skip root if it was auto-skipped)

    setLevels((prev) => {
      const next = prev.slice(0, levelIdx);
      // Add a loading placeholder
      next.push({
        level: adminLevels[levelIdx] || adminLevels[adminLevels.length - 1],
        options: [],
        selected: "",
        loading: true,
      });
      return next;
    });

    const params: Record<string, string> = { project };
    if (parentRegion) params.parent_region = parentRegion;

    const res = await apiCall<any>("get_region_children", params);
    if (res?.status === "success") {
      const options: RegionOption[] = res.data || [];
      if (options.length === 0) {
        // No children - remove the loading level
        setLevels((prev) => prev.slice(0, levelIdx));
        return;
      }
      // Find the matching admin level by the returned administrative_level
      const returnedLevel = options[0]?.administrative_level;
      const matchedLevel = adminLevels.find((l) => l.name === returnedLevel);
      const actualIdx = matchedLevel
        ? adminLevels.indexOf(matchedLevel) - getSkippedLevels()
        : levelIdx;

      setLevels((prev) => {
        const next = prev.slice(0, actualIdx >= 0 ? actualIdx : levelIdx);
        next.push({
          level: matchedLevel || adminLevels[levelIdx] || adminLevels[0],
          options,
          selected: "",
          loading: false,
        });
        return next;
      });
    } else {
      setLevels((prev) => prev.slice(0, levelIdx));
    }
  };

  // How many top levels are skipped (e.g., single root "Rwanda")
  const getSkippedLevels = () => {
    // The API auto-skips single-root levels, so the first visible level
    // is determined by the first response's administrative_level
    if (levels.length > 0 && levels[0].options.length > 0) {
      const firstReturnedLevel = levels[0].options[0].administrative_level;
      const idx = adminLevels.findIndex((l) => l.name === firstReturnedLevel);
      return idx >= 0 ? idx : 0;
    }
    return 0;
  };

  const handleSelect = (levelIdx: number, regionName: string) => {
    // Update selection at this level
    setLevels((prev) => {
      const next = prev.slice(0, levelIdx + 1);
      next[levelIdx] = { ...next[levelIdx], selected: regionName };
      return next;
    });

    // Check if this is the last admin level
    const selectedOption = levels[levelIdx]?.options.find((o) => o.name === regionName);
    const selectedAdminLevel = selectedOption?.administrative_level;
    const lastAdminLevel = adminLevels[adminLevels.length - 1];

    if (selectedAdminLevel === lastAdminLevel.name) {
      // This is the leaf level - set as final value
      onChange(regionName);
    } else {
      // Load children
      onChange(""); // Clear until leaf is selected
      loadChildren(regionName, levelIdx + 1);
    }
  };

  if (!project || adminLevels.length === 0) {
    return (
      <p className="text-sm text-grm-muted text-center py-4">
        {__("No regions found")}
      </p>
    );
  }

  return (
    <div className="space-y-4">
      {levels.map((lvl, idx) => (
        <div key={`${lvl.level.name}-${idx}`}>
          <label className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-1.5 block">
            {__(lvl.level.level_name)}
          </label>

          {lvl.loading ? (
            <div className="flex items-center justify-center py-3">
              <Loader2 className="w-4 h-4 animate-spin text-primary-500" />
            </div>
          ) : (
            <div className="relative">
              <select
                value={lvl.selected}
                onChange={(e) => handleSelect(idx, e.target.value)}
                className={`w-full appearance-none p-2.5 pr-8 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 ${
                  lvl.selected
                    ? "border-primary-500 bg-primary-50"
                    : "border-gray-200"
                }`}
              >
                <option value="">
                  — {__("Select")} {__(lvl.level.level_name)} —
                </option>
                {lvl.options.map((r) => (
                  <option key={r.name} value={r.name}>
                    {r.region_name}
                  </option>
                ))}
              </select>
              <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
            </div>
          )}
        </div>
      ))}

      {/* Show selected path summary */}
      {value && levels.length > 0 && (
        <div className="flex items-center gap-1.5 text-xs text-primary-700 bg-primary-50 rounded-lg p-2.5">
          <MapPin className="w-3.5 h-3.5 flex-shrink-0" />
          <span>
            {levels
              .filter((l) => l.selected)
              .map((l) => l.options.find((o) => o.name === l.selected)?.region_name)
              .filter(Boolean)
              .join(" → ")}
          </span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const TOTAL_STEPS = 6;

export default function SubmitPage() {
  const { __ } = useTranslate();

  // --- State ---
  const [step, setStep] = useState(1);
  const [config, setConfig] = useState<SubmissionConfig | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [categories, setCategories] = useState<OptionItem[]>([]);
  const [issueTypes, setIssueTypes] = useState<OptionItem[]>([]);
  const [adminLevels, setAdminLevels] = useState<AdminLevel[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [otpSent, setOtpSent] = useState(false);
  const [otpSending, setOtpSending] = useState(false);
  const [turnstileToken, setTurnstileToken] = useState("");
  const [trackingCode, setTrackingCode] = useState("");
  const [copied, setCopied] = useState(false);

  const [form, setForm] = useState<FormData>({
    project: "",
    category: "",
    issueType: "",
    region: "",
    issueDate: new Date().toISOString().slice(0, 10),
    description: "",
    contactMedium: "anonymous",
    phone: "",
    otp: "",
    contactInfoType: "phone_number",
    contactInformation: "",
    citizenName: "",
    gender: "",
  });

  const setField = useCallback(
    <K extends keyof FormData>(key: K, value: FormData[K]) =>
      setForm((prev) => ({ ...prev, [key]: value })),
    [],
  );

  // --- Load config + projects on mount ---
  useEffect(() => {
    apiCall<any>("get_submission_config").then((res) => {
      if (res?.status === "success") setConfig(res.data);
    });
    apiCall<any>("get_submission_options").then((res) => {
      if (res?.status === "success") setProjects(res.data.projects || []);
    });
  }, []);

  // --- Load options when project changes ---
  useEffect(() => {
    if (!form.project) {
      setCategories([]);
      setIssueTypes([]);
      setAdminLevels([]);
      return;
    }
    setOptionsLoading(true);
    apiCall<any>("get_submission_options", { project: form.project }).then((res) => {
      if (res?.status === "success") {
        setCategories(res.data.categories || []);
        setIssueTypes(res.data.issue_types || []);
        setAdminLevels(res.data.admin_levels || []);
      }
      setOptionsLoading(false);
    });
  }, [form.project]);

  // --- Compute actual steps (skip verify if not needed, skip region if no levels) ---
  const needsVerifyStep = config?.otp_enabled || !!config?.turnstile_site_key;
  const hasRegions = adminLevels.length > 0;
  const totalVisibleSteps = (needsVerifyStep ? TOTAL_STEPS : TOTAL_STEPS - 1) - (hasRegions ? 0 : 1);

  // Map logical step to display step accounting for skipped steps
  const displayStep = (s: number) => {
    let d = s;
    if (!hasRegions && s >= 3) d--;
    if (!needsVerifyStep && d >= 6) d--;
    return d;
  };

  // --- Step validation ---
  const isStepValid = (s: number): boolean => {
    switch (s) {
      case 1:
        return !!form.project;
      case 2:
        return !!form.category && !!form.issueType;
      case 3:
        if (!hasRegions) return !!form.issueDate && form.description.trim().length >= 10;
        return !!form.region;
      case 4:
        if (!hasRegions) {
          // This is contact step
          if (form.contactMedium === "updates") return !!form.phone;
          return true;
        }
        return !!form.issueDate && form.description.trim().length >= 10;
      case 5:
        if (!hasRegions) {
          // This is verify step (or submit step)
          if (config?.otp_enabled && form.contactMedium === "updates")
            return form.otp.length === 6;
          return true;
        }
        if (form.contactMedium === "updates") return !!form.phone;
        return true;
      case 6:
        if (config?.otp_enabled && form.contactMedium === "updates")
          return form.otp.length === 6;
        return true;
      default:
        return true;
    }
  };

  // --- Navigation ---
  const nextStep = () => {
    setError("");
    let next = step + 1;
    // Skip region step if no admin levels
    if (next === 3 && !hasRegions) next++;
    // Skip verify step if not needed
    if (next === 6 && !needsVerifyStep) next = 7;
    setStep(next);
  };

  const prevStep = () => {
    setError("");
    let prev = step - 1;
    if (prev === 6 && !needsVerifyStep) prev = 5;
    if (prev === 3 && !hasRegions) prev = 2;
    setStep(prev);
  };

  // --- Send OTP ---
  const handleSendOtp = async () => {
    setOtpSending(true);
    setError("");
    try {
      const res = await apiCall<any>("send_otp", { phone: form.phone });
      if (res?.status === "success") {
        setOtpSent(true);
      } else {
        setError(res?.message || __("Failed to send code"));
      }
    } catch {
      setError(__("Failed to send code"));
    }
    setOtpSending(false);
  };

  // --- Submit ---
  const handleSubmit = async () => {
    setSubmitting(true);
    setError("");
    try {
      const payload: Record<string, any> = {
        project: form.project,
        category: form.category,
        issue_type: form.issueType,
        administrative_region: form.region,
        issue_date: form.issueDate,
        description: form.description,
        contact_medium: form.contactMedium,
      };

      if (form.contactMedium === "updates") {
        payload.phone = form.phone;
        payload.contact_info_type = form.contactInfoType;
        payload.contact_information = form.contactInformation || form.phone;
        payload.citizen_name = form.citizenName;
        payload.gender = form.gender;
      }

      if (form.otp) payload.otp_code = form.otp;
      if (turnstileToken) payload.turnstile_token = turnstileToken;

      const res = await apiCall<any>("submit_grievance", payload);
      if (res?.status === "success") {
        setTrackingCode(res.tracking_code);
        setStep(7);
      } else {
        setError(res?.message || __("Submission failed. Please try again."));
      }
    } catch {
      setError(__("An error occurred. Please try again."));
    }
    setSubmitting(false);
  };

  // --- Copy tracking code ---
  const copyCode = () => {
    navigator.clipboard.writeText(trackingCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // --- Reset form ---
  const resetForm = () => {
    setStep(1);
    setForm({
      project: "",
      category: "",
      issueType: "",
      region: "",
      issueDate: new Date().toISOString().slice(0, 10),
      description: "",
      contactMedium: "anonymous",
      phone: "",
      otp: "",
      contactInfoType: "phone_number",
      contactInformation: "",
      citizenName: "",
      gender: "",
    });
    setError("");
    setOtpSent(false);
    setTurnstileToken("");
    setTrackingCode("");
  };

  // --- STEP RENDERERS ---

  const renderStep1 = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">{__("Select Project")}</h2>
      <p className="text-sm text-grm-muted mb-4">
        {__("Which project does your complaint relate to?")}
      </p>
      <div className="space-y-2">
        {projects.map((p) => (
          <button
            key={p.name}
            onClick={() => {
              if (form.project !== p.name) {
                setField("category", "");
                setField("issueType", "");
                setField("region", "");
              }
              setField("project", p.name);
            }}
            className={`w-full text-left p-3 rounded-lg border transition-all ${
              form.project === p.name
                ? "border-primary-500 bg-primary-50"
                : "border-gray-200 hover:border-primary-300"
            }`}
          >
            <span className="text-sm font-medium text-gray-900">{p.title}</span>
            {p.project_code !== p.title && (
              <span className="block text-xs text-grm-muted">{p.project_code}</span>
            )}
          </button>
        ))}
        {projects.length > 1 && (
          <button
            onClick={() => {
              if (form.project !== projects[0].name) {
                setField("category", "");
                setField("issueType", "");
                setField("region", "");
              }
              setField("project", projects[0].name);
            }}
            className={`w-full text-left p-3 rounded-lg border border-dashed transition-all ${
              form.project === projects[0].name
                ? "border-primary-500 bg-primary-50"
                : "border-gray-300 hover:border-primary-300"
            }`}
          >
            <span className="text-sm font-medium text-primary-700">{__("I don't know")}</span>
            <span className="block text-xs text-grm-muted mt-0.5">
              {__("We'll use the default project")}
            </span>
          </button>
        )}
      </div>
    </div>
  );

  const renderStep2 = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">
        {__("Category & Issue Type")}
      </h2>
      <p className="text-sm text-grm-muted mb-4">{__("What is your complaint about?")}</p>

      {optionsLoading ? (
        <div className="flex items-center justify-center py-8">
          <Loader2 className="w-5 h-5 animate-spin text-primary-500" />
        </div>
      ) : (
        <>
          <label className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2 block">
            {__("Category")}
          </label>
          {categories.length === 0 ? (
            <p className="text-sm text-grm-muted mb-4">{__("No categories found")}</p>
          ) : (
            <div className="grid grid-cols-2 gap-2 mb-4">
              {categories.map((c) => (
                <button
                  key={c.name}
                  onClick={() => setField("category", c.name)}
                  className={`text-left p-2.5 rounded-lg border text-sm transition-all ${
                    form.category === c.name
                      ? "border-primary-500 bg-primary-50 font-medium"
                      : "border-gray-200 hover:border-primary-300"
                  }`}
                >
                  {c.category_name}
                </button>
              ))}
            </div>
          )}

          <label className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-2 block">
            {__("Issue Type")}
          </label>
          {issueTypes.length === 0 ? (
            <p className="text-sm text-grm-muted">{__("No issue types found")}</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {issueTypes.map((t) => (
                <button
                  key={t.name}
                  onClick={() => setField("issueType", t.name)}
                  className={`text-left p-2.5 rounded-lg border text-sm transition-all ${
                    form.issueType === t.name
                      ? "border-primary-500 bg-primary-50 font-medium"
                      : "border-gray-200 hover:border-primary-300"
                  }`}
                >
                  {t.issue_type_name}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );

  const renderStep3 = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">{__("Select Region")}</h2>
      <p className="text-sm text-grm-muted mb-4">{__("Where did the issue occur?")}</p>

      <CascadingRegionSelector
        project={form.project}
        adminLevels={adminLevels}
        value={form.region}
        onChange={(v) => setField("region", v)}
        __={__}
      />
    </div>
  );

  const renderStep4 = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">{__("Describe the Issue")}</h2>
      <p className="text-sm text-grm-muted mb-4">
        {__("Please describe your complaint in detail")}
      </p>

      <div className="mb-4">
        <label className="text-xs font-semibold text-gray-700 mb-1 block">
          {__("When did this happen?")} *
        </label>
        <input
          type="date"
          value={form.issueDate}
          max={new Date().toISOString().slice(0, 10)}
          onChange={(e) => setField("issueDate", e.target.value)}
          className="w-full p-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>

      <div>
        <label className="text-xs font-semibold text-gray-700 mb-1 block">
          {__("Description")} *
        </label>
        <textarea
          value={form.description}
          onChange={(e) => setField("description", e.target.value)}
          maxLength={5000}
          rows={5}
          placeholder={__("Describe what happened, when, and how it affected you...")}
          className="w-full p-3 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 resize-none"
        />
        <div className="flex justify-between mt-1">
          <span className="text-xs text-grm-muted">
            {form.description.length < 10 ? __("Minimum 10 characters") : ""}
          </span>
          <span className="text-xs text-grm-muted">{form.description.length}/5000</span>
        </div>
      </div>
    </div>
  );

  const renderStep5 = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">
        {__("Contact Information")}
      </h2>
      <p className="text-sm text-grm-muted mb-4">
        {__("How would you like to be contacted?")}
      </p>

      <div className="space-y-2 mb-4">
        <button
          onClick={() => setField("contactMedium", "anonymous")}
          className={`w-full text-left p-3 rounded-lg border transition-all ${
            form.contactMedium === "anonymous"
              ? "border-primary-500 bg-primary-50"
              : "border-gray-200 hover:border-primary-300"
          }`}
        >
          <span className="text-sm font-medium text-gray-900">
            {__("Stay anonymous")}
          </span>
          <span className="block text-xs text-grm-muted mt-0.5">
            {__("Your complaint will be processed without contact information")}
          </span>
        </button>

        <button
          onClick={() => setField("contactMedium", "updates")}
          className={`w-full text-left p-3 rounded-lg border transition-all ${
            form.contactMedium === "updates"
              ? "border-primary-500 bg-primary-50"
              : "border-gray-200 hover:border-primary-300"
          }`}
        >
          <span className="text-sm font-medium text-gray-900">
            {__("I want updates")}
          </span>
          <span className="block text-xs text-grm-muted mt-0.5">
            {__("Provide your contact details to receive status updates")}
          </span>
        </button>
      </div>

      {form.contactMedium === "updates" && (
        <div className="space-y-3 border-t border-gray-100 pt-4">
          <div>
            <label className="text-xs font-semibold text-gray-700 mb-1 block">
              {__("Phone Number")} *
            </label>
            <input
              type="tel"
              value={form.phone}
              onChange={(e) => setField("phone", e.target.value)}
              placeholder="+250..."
              className="w-full p-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-700 mb-1 block">
              {__("Preferred Contact Method")}
            </label>
            <div className="flex gap-2">
              {[
                { value: "phone_number", label: __("Phone") },
                { value: "email", label: __("Email") },
                { value: "whatsapp", label: "WhatsApp" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setField("contactInfoType", opt.value)}
                  className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                    form.contactInfoType === opt.value
                      ? "border-primary-500 bg-primary-50 font-medium"
                      : "border-gray-200 hover:border-primary-300"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>

          {form.contactInfoType === "email" && (
            <div>
              <label className="text-xs font-semibold text-gray-700 mb-1 block">
                {__("Email Address")}
              </label>
              <input
                type="email"
                value={form.contactInformation}
                onChange={(e) => setField("contactInformation", e.target.value)}
                placeholder="email@example.com"
                className="w-full p-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
          )}

          <div>
            <label className="text-xs font-semibold text-gray-700 mb-1 block">
              {__("Your Name")} ({__("optional")})
            </label>
            <input
              type="text"
              value={form.citizenName}
              onChange={(e) => setField("citizenName", e.target.value)}
              className="w-full p-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-gray-700 mb-1 block">
              {__("Gender")} ({__("optional")})
            </label>
            <div className="flex gap-2">
              {[
                { value: "male", label: __("Male") },
                { value: "female", label: __("Female") },
                { value: "other", label: __("Other") },
              ].map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setField("gender", opt.value)}
                  className={`px-3 py-1.5 rounded-lg border text-xs transition-all ${
                    form.gender === opt.value
                      ? "border-primary-500 bg-primary-50 font-medium"
                      : "border-gray-200 hover:border-primary-300"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderStep6 = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">{__("Verify & Submit")}</h2>
      <p className="text-sm text-grm-muted mb-4">
        {__("Complete verification to submit your complaint")}
      </p>

      {config?.otp_enabled && form.contactMedium === "updates" && form.phone && (
        <div className="mb-4">
          {!otpSent ? (
            <button
              onClick={handleSendOtp}
              disabled={otpSending}
              className="w-full py-2.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
            >
              {otpSending ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {__("Sending...")}
                </span>
              ) : (
                __("Send verification code to {0}").replace("{0}", form.phone)
              )}
            </button>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-gray-700">
                {__("Enter the 6-digit code sent to {0}").replace("{0}", form.phone)}
              </p>
              <input
                type="text"
                value={form.otp}
                onChange={(e) => {
                  const val = e.target.value.replace(/\D/g, "").slice(0, 6);
                  setField("otp", val);
                }}
                placeholder="000000"
                maxLength={6}
                className="w-full p-2.5 border border-gray-200 rounded-lg text-center text-lg font-mono tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
              <button
                onClick={() => {
                  setOtpSent(false);
                  setField("otp", "");
                }}
                className="text-xs text-primary-500 hover:underline"
              >
                {__("Resend code")}
              </button>
            </div>
          )}
        </div>
      )}

      {config?.turnstile_site_key && (
        <TurnstileWidget siteKey={config.turnstile_site_key} onToken={setTurnstileToken} />
      )}

      <button
        onClick={handleSubmit}
        disabled={submitting || !isStepValid(step)}
        className="w-full mt-4 py-3 bg-primary-500 hover:bg-primary-700 text-white rounded-lg text-sm font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {submitting ? (
          <span className="flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin" />
            {__("Submitting...")}
          </span>
        ) : (
          __("Submit Complaint")
        )}
      </button>
    </div>
  );

  const renderResult = () => (
    <div className="text-center py-6">
      <div className="w-16 h-16 rounded-full bg-primary-100 flex items-center justify-center mx-auto mb-4">
        <CheckCircle className="w-8 h-8 text-primary-500" />
      </div>

      <h2 className="text-lg font-bold text-gray-900 mb-2">
        {__("Complaint Submitted Successfully")}
      </h2>
      <p className="text-sm text-grm-muted mb-6">
        {__("Save your tracking code to check the status of your complaint")}
      </p>

      <div className="bg-gray-50 rounded-xl p-4 mb-4 inline-block">
        <p className="text-xs text-grm-muted mb-1">{__("Tracking Code")}</p>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold font-mono text-gray-900 tracking-wider">
            {trackingCode}
          </span>
          <button
            onClick={copyCode}
            className="p-1.5 hover:bg-gray-200 rounded-lg transition-all"
            title={__("Copy")}
          >
            {copied ? (
              <CheckCircle className="w-4 h-4 text-primary-500" />
            ) : (
              <Copy className="w-4 h-4 text-grm-muted" />
            )}
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-2 mt-6">
        <a
          href="/grm-portal/track"
          className="py-2.5 bg-primary-500 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-all block"
        >
          {__("Track Your Complaint")}
        </a>
        <button
          onClick={resetForm}
          className="py-2.5 border border-gray-200 hover:bg-gray-50 rounded-lg text-sm text-gray-700 transition-all"
        >
          {__("Submit Another Complaint")}
        </button>
      </div>
    </div>
  );

  // --- Step router ---
  const renderCurrentStep = () => {
    if (step === 7) return renderResult();
    switch (step) {
      case 1:
        return renderStep1();
      case 2:
        return renderStep2();
      case 3:
        return hasRegions ? renderStep3() : renderStep4();
      case 4:
        return hasRegions ? renderStep4() : renderStep5();
      case 5:
        return hasRegions ? renderStep5() : renderStep6();
      case 6:
        return renderStep6();
      default:
        return null;
    }
  };

  // Determine if current step should show a submit button instead of next
  const effectiveLastInputStep = needsVerifyStep ? false : step === 5;
  const isVerifyStep = step === 6 && needsVerifyStep;

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <div className="text-center mb-4">
        <h1 className="text-xl font-bold text-gray-900 mb-1">
          {__("Submit a Grievance")}
        </h1>
        {step <= TOTAL_STEPS && (
          <p className="text-xs text-grm-muted">
            {__("Step {0}").replace("{0}", String(displayStep(step)))} /{" "}
            {totalVisibleSteps}
          </p>
        )}
      </div>

      {step <= TOTAL_STEPS && (
        <ProgressDots current={displayStep(step)} total={totalVisibleSteps} />
      )}

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
          <span className="text-sm text-red-700">{error}</span>
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        {renderCurrentStep()}
      </div>

      {step < 7 && (
        <div className="flex gap-3 mt-4">
          {step > 1 && (
            <button
              onClick={prevStep}
              className="flex items-center gap-1 px-4 py-2.5 border border-gray-200 hover:bg-gray-50 rounded-lg text-sm text-gray-700 transition-all"
            >
              <ChevronLeft className="w-4 h-4" />
              {__("Back")}
            </button>
          )}

          {!isVerifyStep && !effectiveLastInputStep && step < 6 && (
            <button
              onClick={nextStep}
              disabled={!isStepValid(step)}
              className="flex-1 flex items-center justify-center gap-1 px-4 py-2.5 bg-primary-500 hover:bg-primary-700 text-white rounded-lg text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {__("Next")}
              <ChevronRight className="w-4 h-4" />
            </button>
          )}

          {effectiveLastInputStep && (
            <button
              onClick={handleSubmit}
              disabled={submitting || !isStepValid(step)}
              className="flex-1 py-2.5 bg-primary-500 hover:bg-primary-700 text-white rounded-lg text-sm font-semibold transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {__("Submitting...")}
                </span>
              ) : (
                __("Submit Complaint")
              )}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
