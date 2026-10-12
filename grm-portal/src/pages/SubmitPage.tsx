import { useState, useEffect, useCallback, useContext, useMemo, useRef } from "react";
import {
  ChevronLeft,
  ChevronRight,
  CheckCircle,
  Copy,
  Loader2,
  AlertCircle,
  MapPin,
  ChevronDown,
  FolderOpen,
} from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { FrappeContext, FrappeConfig } from "frappe-react-sdk";
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
// API helpers (frappe-react-sdk)
// ---------------------------------------------------------------------------

const POST_METHODS = new Set(["send_otp", "submit_grievance"]);

function useApiCall() {
  const { call } = useContext(FrappeContext) as FrappeConfig;
  return useCallback(
    async <T = any>(method: string, params?: Record<string, any>): Promise<T> => {
      const path = `egrm.api.public_submit.${method}`;
      const resp = POST_METHODS.has(method)
        ? await call.post<{ message: T }>(path, params)
        : await call.get<{ message: T }>(path, params);
      return resp?.message as T;
    },
    [call]
  );
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

const TURNSTILE_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js";

function TurnstileWidget({
  siteKey,
  onToken,
  __,
}: {
  siteKey: string;
  onToken: (token: string) => void;
  __: (s: string) => string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  // The Turnstile script loads asynchronously and can be blocked outright by a
  // network filter. Checking for it once on mount and giving up left a blank
  // space where the only route to submitting the complaint was supposed to be,
  // with nothing on screen to say so. Wait for it, then say so.
  const [state, setState] = useState<"waiting" | "ready" | "unavailable">(
    window.turnstile ? "ready" : "waiting",
  );

  useEffect(() => {
    if (state !== "waiting") return;
    // Loaded here rather than from index.html. Every visitor used to fetch
    // and run Cloudflare's script on the home page, the tracking page and
    // the dashboard, none of which have a challenge on them -- a third-party
    // request on first paint for a widget almost nobody reaches.
    if (!document.querySelector(`script[src="${TURNSTILE_SRC}"]`)) {
      const el = document.createElement("script");
      el.src = TURNSTILE_SRC;
      el.async = true;
      el.defer = true;
      document.head.appendChild(el);
    }
    const started = Date.now();
    const timer = window.setInterval(() => {
      if (window.turnstile) {
        setState("ready");
        window.clearInterval(timer);
      } else if (Date.now() - started > 8000) {
        setState("unavailable");
        window.clearInterval(timer);
      }
    }, 250);
    return () => window.clearInterval(timer);
  }, [state]);

  useEffect(() => {
    if (state !== "ready" || !containerRef.current || !window.turnstile) return;
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
  }, [siteKey, onToken, state]);

  if (state === "unavailable") {
    return (
      <p
        role="alert"
        className="my-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900"
      >
        {__(
          "The security check could not load. Check your connection and reload the page, or submit your complaint through the mobile app.",
        )}
      </p>
    );
  }

  if (state === "waiting") {
    return (
      <p role="status" className="my-4 text-center text-sm text-grm-secondary">
        {__("Loading security check...")}
      </p>
    );
  }

  return <div ref={containerRef} className="flex justify-center my-4" />;
}

// ---------------------------------------------------------------------------
// Progress Dots
// ---------------------------------------------------------------------------

function ProgressDots({
  current,
  total,
  indeterminate = false,
}: {
  current: number;
  total: number;
  indeterminate?: boolean;
}) {
  return (
    <div className="flex items-center justify-center gap-2 mb-6">
      {Array.from({ length: total }, (_, i) => {
        const step = i + 1;
        const isActive = step === current;
        const isDone = step < current;
        // Whether a region step exists depends on the project, which hasn't
        // been chosen yet. Draw that trailing step as provisional instead of
        // silently adding or dropping a dot once the answer arrives.
        const isProvisional = indeterminate && step === total;
        return (
          <div
            key={step}
            className={`w-2.5 h-2.5 rounded-full transition-all ${
              isProvisional
                ? "border border-dashed border-grm-field"
                : isActive
                  ? "bg-primary-700 scale-125"
                  : isDone
                    ? "bg-primary-600"
                    : "bg-gray-500"
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
  const apiCall = useApiCall();
  // Each level holds: { selected region name, options[] }
  const [levels, setLevels] = useState<
    { level: AdminLevel; options: RegionOption[]; selected: string; loading: boolean }[]
  >([]);
  const [loadError, setLoadError] = useState(false);

  // Load first level on mount / project change.
  //
  // The cascade lives in this component's state, and only the active step is
  // mounted -- so stepping forward and back, or reloading, used to drop the
  // citizen on an empty dropdown while `value` still held the region they had
  // picked. The screen said nothing was selected, Next stayed enabled, and the
  // complaint filed against a region nothing on the page named. When a value
  // survives, rebuild the cascade that produced it rather than starting over.
  useEffect(() => {
    if (!project || adminLevels.length === 0) {
      setLevels([]);
      return;
    }
    if (value) restorePath(value);
    else loadChildren(null, 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project, adminLevels]);

  // `silent` suppresses the loading placeholder. Used when we are probing past
  // the end of the level schema: most of those probes come back empty, and a
  // dropdown that appears, spins, and vanishes is worse than no dropdown.
  const loadChildren = async (
    parentRegion: string | null,
    levelIdx: number,
    silent = false
  ) => {
    // Find which admin level this corresponds to
    // The API returns children - their admin_level tells us which level they are
    // We start from the first visible level (skip root if it was auto-skipped)

    if (!silent) {
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
    }

    const params: Record<string, string> = { project };
    if (parentRegion) params.parent_region = parentRegion;

    // A rejected request used to escape this function, leaving the level stuck
    // on its loading placeholder with no way forward and nothing said.
    let res: any;
    try {
      res = await apiCall<any>("get_region_children", params);
    } catch {
      if (!silent) setLevels((prev) => prev.slice(0, levelIdx));
      setLoadError(true);
      return;
    }
    setLoadError(false);
    if (res?.status === "success") {
      const options: RegionOption[] = res.data || [];
      if (options.length === 0) {
        // The level schema is project-wide, so it can promise a level deeper
        // than this particular branch of the tree actually goes. The old code
        // dropped the empty dropdown and returned, leaving region === "" (set
        // by handleSelect before it called us) with no control left to touch:
        // a step that looks finished, a Next button that never enables, and
        // nothing on screen saying why. The deepest region the citizen did
        // pick is the answer.
        if (!silent) setLevels((prev) => prev.slice(0, levelIdx));
        if (parentRegion) onChange(parentRegion);
        return;
      }
      // Find the matching admin level by the returned administrative_level
      const returnedLevel = options[0]?.administrative_level;
      const matchedLevel = adminLevels.find((l) => l.name === returnedLevel);
      const actualIdx = matchedLevel
        ? adminLevels.indexOf(matchedLevel) - getSkippedLevels()
        : levelIdx;

      // Remapping by declared level is only sound while the tree is exactly as
      // deep as the schema says. On a silent probe it is not: these children
      // sit below the last declared level and carry its name, so actualIdx
      // points back at the dropdown the citizen just used and the slice would
      // delete it. Append where we were asked to instead.
      const insertAt = silent ? levelIdx : actualIdx >= 0 ? actualIdx : levelIdx;

      setLevels((prev) => {
        const next = prev.slice(0, insertAt);
        next.push({
          level: matchedLevel || adminLevels[levelIdx] || adminLevels[0],
          options,
          selected: "",
          loading: false,
        });
        return next;
      });
      // The optimistic commit made before a silent probe assumed this was the
      // leaf. It is not -- take it back until the citizen picks from the
      // dropdown we are about to show.
      if (silent) onChange("");
    } else {
      if (!silent) setLevels((prev) => prev.slice(0, levelIdx));
      if (silent && parentRegion) onChange(parentRegion);
    }
  };

  // Rebuild every dropdown down to `regionName`, in one request. Falling back
  // to the first level alone would be the old behaviour; clearing the value
  // alongside it is the part that matters, because a restore that silently
  // fails must not leave the form holding a region the citizen can no longer
  // see or change.
  const restorePath = async (regionName: string) => {
    setLevels([
      { level: adminLevels[0], options: [], selected: "", loading: true },
    ]);

    let res: any;
    try {
      res = await apiCall<any>("get_region_path", { project, region: regionName });
    } catch {
      setLoadError(true);
      setLevels([]);
      onChange("");
      return;
    }

    const path: {
      administrative_level: string;
      selected: string;
      options: RegionOption[];
    }[] = res?.status === "success" ? res.data || [] : [];

    // No path means the stored region is gone, or belongs to another project.
    // Start the citizen over honestly instead of restoring a lie.
    if (path.length === 0) {
      onChange("");
      loadChildren(null, 0);
      return;
    }

    setLoadError(false);
    setLevels(
      path.map((p) => ({
        level:
          adminLevels.find((l) => l.name === p.administrative_level) ||
          adminLevels[0],
        options: p.options,
        selected: p.selected,
        loading: false,
      }))
    );
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

    // Whether to go deeper is decided by the region tree, not by the level
    // schema. The schema is a project-wide promise that the data routinely
    // breaks in both directions: RDAP, for instance, declares only PIU and
    // Province, yet carries districts underneath its provinces. Stopping at
    // "this region is at the last declared level" hid every one of them --
    // the citizen picked a province and the form called it done. So always
    // ask whether this region has children; get_region_children returns []
    // for a true leaf, and loadChildren commits the selection on empty.
    const selectedOption = levels[levelIdx]?.options.find((o) => o.name === regionName);
    const selectedAdminLevel = selectedOption?.administrative_level;
    const lastAdminLevel = adminLevels[adminLevels.length - 1];
    const beyondSchema = selectedAdminLevel === lastAdminLevel.name;

    // Not a leaf as far as the schema knows, so a child dropdown is expected:
    // show it loading. Past the schema's end it is a probe, and most probes
    // come back empty, so keep it off-screen until it has something to offer.
    onChange(beyondSchema ? regionName : "");
    loadChildren(regionName, levelIdx + 1, beyondSchema);
  };

  if (!project || adminLevels.length === 0) {
    return (
      <p className="text-sm text-grm-secondary text-center py-4">
        {__("No regions found")}
      </p>
    );
  }

  return (
    <div className="space-y-4" aria-busy={levels.some((l) => l.loading)}>
      {loadError && (
        <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
          {__("Could not load regions. Check your connection and try again.")}
        </p>
      )}

      {levels.map((lvl, idx) => (
        <div key={`${lvl.level.name}-${idx}`}>
          <label
            htmlFor={`region-level-${idx}`}
            className="text-sm font-semibold text-gray-800 mb-1.5 block"
          >
            {__(lvl.level.level_name)}
          </label>

          {/* The select stays mounted while its options load. Swapping it
              for a spinner left the label above pointing at an id that was
              not in the document, and made the row jump as the control came
              and went. It is disabled instead, and says so. */}
          <div className="relative">
            <select
              id={`region-level-${idx}`}
              value={lvl.selected}
              disabled={lvl.loading}
              aria-busy={lvl.loading}
              onChange={(e) => handleSelect(idx, e.target.value)}
              className={`w-full min-h-[48px] appearance-none p-2.5 pr-8 border rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-primary-700 disabled:bg-gray-50 disabled:text-grm-secondary ${
                lvl.selected
                  ? "border-primary-700 bg-primary-50"
                  : "border-grm-field"
              }`}
            >
              <option value="">
                {lvl.loading
                  ? __("Loading...")
                  : `— ${__("Select")} ${__(lvl.level.level_name)} —`}
              </option>
              {!lvl.loading &&
                lvl.options.map((r) => (
                  <option key={r.name} value={r.name}>
                    {__(r.region_name)}
                  </option>
                ))}
            </select>
            {lvl.loading ? (
              <Loader2
                className="absolute right-2.5 top-1/2 w-4 h-4 -translate-y-1/2 animate-spin text-primary-700"
                aria-hidden="true"
              />
            ) : (
              <ChevronDown
                className="absolute right-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500 pointer-events-none"
                aria-hidden="true"
              />
            )}
          </div>
        </div>
      ))}

      {/* Show selected path summary */}
      {value && levels.length > 0 && (
        <div className="flex items-center gap-1.5 text-sm text-primary-800 bg-primary-50 rounded-lg p-2.5">
          <MapPin className="w-4 h-4 flex-shrink-0" aria-hidden="true" />
          <span>
            {levels
              .filter((l) => l.selected)
              .map((l) => {
                const name = l.options.find((o) => o.name === l.selected)?.region_name;
                return name ? __(name) : null;
              })
              .filter(Boolean)
              .join(" → ")}
          </span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Draft persistence
// ---------------------------------------------------------------------------

// sessionStorage, deliberately, not localStorage: a half-written grievance is
// sensitive, and this portal is used on shared and public machines. The draft
// survives a reload or a stray Back press and dies with the tab.
const DRAFT_KEY = "grm-portal:submit-draft";

function blankForm(): FormData {
  return {
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
  };
}

function readDraft(): Partial<FormData> {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    return raw ? (JSON.parse(raw) as Partial<FormData>) : {};
  } catch {
    // Private mode, blocked storage, or a stale shape. A missing draft is not
    // worth failing the page over.
    return {};
  }
}

function writeDraft(form: FormData): void {
  try {
    // The one-time code is never written down -- it is short-lived and its
    // whole value is that it stays with the person holding the phone.
    const { otp: _otp, ...rest } = form;
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(rest));
  } catch {}
}

function clearDraft(): void {
  try {
    sessionStorage.removeItem(DRAFT_KEY);
  } catch {}
}

// The tracking code is the only thing the citizen takes away from the whole
// exercise, and it used to live solely in component state on a lazily-mounted
// route: one tap on the success screen's own Track link unmounted the page and
// destroyed it, as did a reload or a tab discard. It outlives the draft that
// carried it, and like the draft it dies with the tab rather than sitting on a
// shared machine.
const CODE_KEY = "grm-portal:tracking-code";

function readCode(): string {
  try {
    return sessionStorage.getItem(CODE_KEY) || "";
  } catch {
    return "";
  }
}

function writeCode(code: string): void {
  try {
    if (code) sessionStorage.setItem(CODE_KEY, code);
    else sessionStorage.removeItem(CODE_KEY);
  } catch {}
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

// The wizard's steps, named rather than numbered. A number says where the
// user is only if you also know which steps this deployment skips; a name
// says it outright.
type StepKey = "project" | "category" | "region" | "describe" | "contact" | "verify";

export default function SubmitPage() {
  const { __ } = useTranslate();
  const apiCall = useApiCall();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedProject = searchParams.get("project") || "";

  // --- State ---
  // The step lives in the URL rather than in component state. Held in state,
  // the device Back button walked straight out of the portal from halfway
  // through the form -- on a phone, the most common way to lose a complaint
  // someone had already spent five minutes writing.
  const urlStep = Number(searchParams.get("step"));
  const step = Number.isFinite(urlStep) && urlStep >= 1 ? Math.floor(urlStep) : 1;
  const setStep = useCallback(
    (next: number, replace = false) => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);
          params.set("step", String(next));
          return params;
        },
        { replace },
      );
    },
    [setSearchParams],
  );
  // True once the project is settled without the user picking it — either the
  // deployment only has one, or they arrived from a project card on the home
  // page. Step 1 then disappears from the wizard entirely.
  const [projectLocked, setProjectLocked] = useState(false);
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
  const [trackingCode, setTrackingCode] = useState(readCode);
  const [copied, setCopied] = useState(false);

  const [form, setForm] = useState<FormData>(() => ({ ...blankForm(), ...readDraft() }));
  // True when "I don't know" was chosen rather than a project being named.
  // Without this the sentinel button and the first project in the list shared
  // one state, so picking the first project lit up both.
  const [projectUnknown, setProjectUnknown] = useState(false);
  const [copyFailed, setCopyFailed] = useState(false);

  // Keep the draft current so a reload, a stray Back press or a phone call
  // taking over the screen does not cost the user their complaint.
  useEffect(() => {
    writeDraft(form);
  }, [form]);

  const setField = useCallback(
    <K extends keyof FormData>(key: K, value: FormData[K]) =>
      setForm((prev) => ({ ...prev, [key]: value })),
    [],
  );

  // --- Load config + projects on mount ---
  useEffect(() => {
    // A rejected call used to disappear silently, leaving an empty project
    // list that looked like a deployment with no projects in it.
    apiCall<any>("get_submission_config")
      .then((res) => {
        if (res?.status === "success") setConfig(res.data);
      })
      .catch(() =>
        setError(__("Could not load the form. Check your connection and reload the page.")),
      );
    apiCall<any>("get_submission_options")
      .then((res) => {
        if (res?.status === "success") setProjects(res.data.projects || []);
      })
      .catch(() =>
        setError(__("Could not load the list of projects. Check your connection and reload the page.")),
      );
  }, []);

  // --- Resolve the project without asking, when there is nothing to ask ---
  // A single-project deployment has no decision to make, and arriving from a
  // project card on the home page has already made it. Either way, jump
  // straight to the first question that actually needs an answer.
  useEffect(() => {
    // Only ever fires before a project is settled, so it cannot pull a user
    // back out of a form they are part-way through.
    if (!projects.length || form.project) return;
    const preselected =
      projects.length === 1
        ? projects[0]
        : projects.find((p) => p.name === requestedProject);
    if (!preselected) return;
    setField("project", preselected.name);
    // The project step leaves the wizard, so step 1 becomes the category
    // step and the index in the URL needs no adjusting.
    setProjectLocked(true);
  }, [projects, requestedProject, form.project, setField]);

  // --- Load options when project changes ---
  useEffect(() => {
    if (!form.project) {
      setCategories([]);
      setIssueTypes([]);
      setAdminLevels([]);
      return;
    }
    setOptionsLoading(true);
    apiCall<any>("get_submission_options", { project: form.project })
      .then((res) => {
        if (res?.status === "success") {
          setCategories(res.data.categories || []);
          setIssueTypes(res.data.issue_types || []);
          setAdminLevels(res.data.admin_levels || []);
        }
      })
      .catch(() =>
        setError(__("Could not load the options for this project. Check your connection and try again.")),
      )
      // Clearing the flag only on success left the spinner turning for the
      // rest of the session whenever the call failed.
      .finally(() => setOptionsLoading(false));
  }, [form.project]);

  // --- The wizard's shape ---
  // Which steps exist depends on the deployment and on the chosen project.
  // That arithmetic used to be repeated in four places -- navigation,
  // rendering, validation and the hint text -- and the copies disagreed: with
  // no administrative regions, navigation skipped the description step that
  // rendering still expected, so a complaint could be filed with an empty
  // body and no validation ever ran on it. One ordered list now answers every
  // question about where the user is.
  const needsVerifyStep = config?.otp_enabled || !!config?.turnstile_site_key;
  const hasRegions = adminLevels.length > 0;

  const activeSteps = useMemo<StepKey[]>(() => {
    const keys: StepKey[] = [];
    if (!projectLocked) keys.push("project");
    keys.push("category");
    if (hasRegions) keys.push("region");
    keys.push("describe", "contact");
    if (needsVerifyStep) keys.push("verify");
    return keys;
  }, [projectLocked, hasRegions, needsVerifyStep]);

  const totalVisibleSteps = activeSteps.length;
  // The step is in the URL, where it can be edited, and the list shortens
  // when the project step drops out. An out-of-range value lands on the
  // nearest real step rather than on a blank card.
  const stepIndex = Math.min(Math.max(step, 1), totalVisibleSteps);
  const stepKey = activeSteps[stepIndex - 1];
  const isLastStep = stepIndex === totalVisibleSteps;

  // `hasRegions` comes from the chosen project's administrative levels, so
  // until a project is picked and its options land, the wizard's length is
  // one of two values. Don't print a total that is about to change.
  const stepCountKnown = !!form.project && !optionsLoading;

  const selectedProject = projects.find((p) => p.name === form.project);

  // --- Step validation ---
  const isStepValid = (key: StepKey | undefined): boolean => {
    switch (key) {
      case "project":
        return !!form.project;
      case "category":
        return !!form.category && !!form.issueType;
      case "region":
        return !!form.region;
      case "describe":
        return !!form.issueDate && form.description.trim().length >= 10;
      case "contact":
        return form.contactMedium === "updates" ? !!form.phone : true;
      case "verify":
        // The bot check has to pass before the server will take the
        // submission, so leaving it out of the step's validity offered an
        // enabled Submit that could only fail -- and fail into an error
        // block the citizen may never scroll up to see.
        if (config?.turnstile_site_key && !turnstileToken) return false;
        if (config?.otp_enabled && form.contactMedium === "updates")
          return form.otp.length === 6;
        return true;
      default:
        return true;
    }
  };

  // A disabled button with no explanation is a dead end: the user can see
  // that they cannot continue but not what is being asked of them. Keyed the
  // same way as isStepValid so the two cannot drift apart.
  const stepHint = (key: StepKey | undefined): string => {
    switch (key) {
      case "project":
        return form.project ? "" : __("Choose the project this complaint relates to.");
      case "category":
        if (!form.category) return __("Choose a category.");
        if (!form.issueType) return __("Choose an issue type.");
        return "";
      case "region":
        return form.region ? "" : __("Select the region where this happened.");
      case "describe":
        return describeHint();
      case "contact":
        return contactHint();
      case "verify":
        return otpHint();
      default:
        return "";
    }
  };

  const describeHint = () => {
    if (!form.issueDate) return __("Enter the date this happened.");
    if (form.description.trim().length < 10)
      return __("Describe what happened in at least 10 characters.");
    return "";
  };

  const contactHint = () =>
    form.contactMedium === "updates" && !form.phone
      ? __("Enter a phone number, or choose to stay anonymous.")
      : "";

  const otpHint = () =>
    config?.otp_enabled && form.contactMedium === "updates" && form.otp.length !== 6
      ? __("Enter the 6-digit code to continue.")
      : "";

  /** The control a step is waiting on, so an incomplete step can put the
   *  cursor on the field rather than just refusing to advance. Steps built
   *  from button groups have no single field and return null; focus stays on
   *  the step panel for those. */
  const missingFieldId = (key: StepKey | undefined): string | null => {
    switch (key) {
      case "region":
        return "region-level-0";
      case "describe":
        return !form.issueDate ? "issue-date" : "issue-description";
      case "contact":
        return "contact-phone";
      case "verify":
        return "otp-code";
      default:
        return null;
    }
  };

  // --- Navigation ---
  const nextStep = () => {
    setError("");
    if (stepIndex < totalVisibleSteps) setStep(stepIndex + 1);
  };

  const prevStep = () => {
    setError("");
    if (stepIndex > 1) setStep(stepIndex - 1);
  };

  /** Enter in any field, and the footer's advance button, both come through
   *  here. An incomplete step is not refused silently: the step hint is
   *  already tied to the button, and focus moves to the field it names. */
  const handleStepSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    if (!isStepValid(stepKey)) {
      const id = missingFieldId(stepKey);
      const el = id ? document.getElementById(id) : null;
      if (el) {
        (el as HTMLElement).focus();
      } else {
        stepRegionRef.current?.focus();
      }
      return;
    }
    if (isLastStep) {
      handleSubmit();
    } else {
      nextStep();
    }
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
        // Written down before the draft is cleared, so a reload, a tab discard
        // or a trip to the track page cannot lose it.
        writeCode(res.tracking_code);
        // The complaint is filed; the draft has served its purpose and should
        // not sit in storage on what may be a shared machine.
        clearDraft();
        // One past the last step, replacing the last wizard step rather than
        // stacking on it: Back must not return to a filled-in form whose
        // complaint has already been filed and would be filed again.
        setStep(totalVisibleSteps + 1, true);
      } else {
        setError(res?.message || __("Submission failed. Please try again."));
      }
    } catch {
      setError(__("An error occurred. Please try again."));
    }
    setSubmitting(false);
  };

  // --- Copy tracking code ---
  const copyCode = async () => {
    // navigator.clipboard is undefined on an insecure origin and the write can
    // be refused outright. Either way the old code claimed success.
    try {
      if (!navigator.clipboard) throw new Error("clipboard unavailable");
      await navigator.clipboard.writeText(trackingCode);
      setCopyFailed(false);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyFailed(true);
    }
  };

  // --- Reset form ---
  const resetForm = () => {
    clearDraft();
    setStep(1);
    setForm({
      ...blankForm(),
      // A locked project survives "Submit Another Complaint" — clearing it
      // would drop the user on a step that is no longer part of the wizard.
      project: projectLocked ? form.project : "",
    });
    setProjectUnknown(false);
    setError("");
    setOtpSent(false);
    setTurnstileToken("");
    setTrackingCode("");
    writeCode("");
    setCopyFailed(false);
  };

  // --- STEP RENDERERS ---

  const chooseProject = (name: string, unknown: boolean) => {
    if (form.project !== name) {
      setField("category", "");
      setField("issueType", "");
      setField("region", "");
    }
    setField("project", name);
    setProjectUnknown(unknown);
  };

  const renderProjectStep = () => (
    <div>
      <h2 id="step1-heading" className="text-lg font-bold text-gray-900 mb-1">
        {__("Select Project")}
      </h2>
      <p className="text-sm text-grm-secondary mb-4">
        {__("Which project does your complaint relate to?")}
      </p>
      <div className="space-y-2" role="group" aria-labelledby="step1-heading">
        {projects.map((p) => {
          const selected = form.project === p.name && !projectUnknown;
          return (
            <button
              key={p.name}
              type="button"
              aria-pressed={selected}
              onClick={() => chooseProject(p.name, false)}
              className={`w-full min-h-[44px] text-left p-3 rounded-lg border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
                selected
                  ? "border-primary-700 bg-primary-50"
                  : "border-grm-field hover:border-primary-700"
              }`}
            >
              <span className="text-sm font-medium text-gray-900">{p.title}</span>
              {p.project_code !== p.title && (
                <span className="block text-sm text-grm-secondary">{p.project_code}</span>
              )}
            </button>
          );
        })}
        {projects.length > 1 && (
          <button
            type="button"
            aria-pressed={projectUnknown}
            onClick={() => chooseProject(projects[0].name, true)}
            className={`w-full min-h-[44px] text-left p-3 rounded-lg border border-dashed transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
              projectUnknown
                ? "border-primary-700 bg-primary-50"
                : "border-gray-500 hover:border-primary-700"
            }`}
          >
            <span className="text-sm font-medium text-primary-800">{__("I don't know")}</span>
            {/* Name the project this actually files against. "The default
                project" told the user nothing and hid the fact that the choice
                was identical to picking the first one in the list. */}
            <span className="block text-sm text-grm-secondary mt-0.5">
              {__("We'll file it under {0} and route it from there").replace(
                "{0}",
                projects[0].title,
              )}
            </span>
          </button>
        )}
      </div>
    </div>
  );

  const renderCategoryStep = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">
        {__("Category & Issue Type")}
      </h2>
      <p className="text-sm text-grm-secondary mb-4">{__("What is your complaint about?")}</p>

      {optionsLoading ? (
        <div className="flex items-center justify-center py-8" role="status">
          <Loader2 className="w-5 h-5 animate-spin text-primary-700" aria-hidden="true" />
          <span className="sr-only">{__("Loading...")}</span>
        </div>
      ) : (
        <>
          <h3 id="category-label" className="text-sm font-semibold text-gray-800 mb-2">
            {__("Category")}
          </h3>
          {categories.length === 0 ? (
            <p className="text-sm text-grm-secondary mb-4">{__("No categories found")}</p>
          ) : (
            <div
              className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-4"
              role="group"
              aria-labelledby="category-label"
            >
              {categories.map((c) => (
                <button
                  key={c.name}
                  type="button"
                  aria-pressed={form.category === c.name}
                  onClick={() => setField("category", c.name)}
                  className={`flex min-h-[44px] items-center text-left p-2.5 rounded-lg border text-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
                    form.category === c.name
                      ? "border-primary-700 bg-primary-50 font-medium"
                      : "border-grm-field hover:border-primary-700"
                  }`}
                >
                  {/* Category and type names are administrator-defined rows,
                      so they are translated through the same dictionary the
                      rest of the portal uses. An admin adds a Translation for
                      the name and it resolves here with no code change. */}
                  {__(c.category_name ?? "")}
                </button>
              ))}
            </div>
          )}

          <h3 id="issue-type-label" className="text-sm font-semibold text-gray-800 mb-2">
            {__("Issue Type")}
          </h3>
          {issueTypes.length === 0 ? (
            <p className="text-sm text-grm-secondary">{__("No issue types found")}</p>
          ) : (
            <div
              className="grid grid-cols-1 sm:grid-cols-2 gap-2"
              role="group"
              aria-labelledby="issue-type-label"
            >
              {issueTypes.map((t) => (
                <button
                  key={t.name}
                  type="button"
                  aria-pressed={form.issueType === t.name}
                  onClick={() => setField("issueType", t.name)}
                  className={`flex min-h-[44px] items-center text-left p-2.5 rounded-lg border text-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
                    form.issueType === t.name
                      ? "border-primary-700 bg-primary-50 font-medium"
                      : "border-grm-field hover:border-primary-700"
                  }`}
                >
                  {__(t.issue_type_name ?? "")}
                </button>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );

  const renderRegionStep = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">{__("Select Region")}</h2>
      <p className="text-sm text-grm-secondary mb-4">{__("Where did the issue occur?")}</p>

      <CascadingRegionSelector
        project={form.project}
        adminLevels={adminLevels}
        value={form.region}
        onChange={(v) => setField("region", v)}
        __={__}
      />
    </div>
  );

  const renderDescribeStep = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">{__("Describe the Issue")}</h2>
      <p className="text-sm text-grm-secondary mb-4">
        {__("Please describe your complaint in detail")}
      </p>

      <div className="mb-4">
        <label htmlFor="issue-date" className="text-sm font-semibold text-gray-800 mb-1 block">
          {__("When did this happen?")} *
        </label>
        <input
          id="issue-date"
          name="issue-date"
          type="date"
          required
          value={form.issueDate}
          max={new Date().toISOString().slice(0, 10)}
          onChange={(e) => setField("issueDate", e.target.value)}
          className="w-full min-h-[48px] p-2.5 border border-grm-field rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-primary-700"
        />
      </div>

      <div>
        <label htmlFor="issue-description" className="text-sm font-semibold text-gray-800 mb-1 block">
          {__("Description")} *
        </label>
        <textarea
          id="issue-description"
          name="issue-description"
          required
          aria-describedby="description-help"
          value={form.description}
          onChange={(e) => setField("description", e.target.value)}
          maxLength={5000}
          rows={5}
          placeholder={__("Describe what happened, when, and how it affected you...")}
          className="w-full p-3 border border-grm-field rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-primary-700 resize-none"
        />
        <div className="flex justify-between gap-3 mt-1" id="description-help">
          <span className="text-sm text-grm-secondary">
            {form.description.length < 10 ? __("Minimum 10 characters") : ""}
          </span>
          <span className="text-sm text-grm-secondary tabular-nums">
            {form.description.length}/5000
          </span>
        </div>
      </div>
    </div>
  );

  const renderContactStep = () => (
    <div>
      <h2 id="contact-heading" className="text-lg font-bold text-gray-900 mb-1">
        {__("Contact Information")}
      </h2>
      <p className="text-sm text-grm-secondary mb-4">
        {__("How would you like to be contacted?")}
      </p>

      <div className="space-y-2 mb-4" role="group" aria-labelledby="contact-heading">
        <button
          type="button"
          aria-pressed={form.contactMedium === "anonymous"}
          onClick={() => setField("contactMedium", "anonymous")}
          className={`w-full min-h-[44px] text-left p-3 rounded-lg border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
            form.contactMedium === "anonymous"
              ? "border-primary-700 bg-primary-50"
              : "border-grm-field hover:border-primary-700"
          }`}
        >
          <span className="text-sm font-medium text-gray-900">
            {__("Stay anonymous")}
          </span>
          <span className="block text-sm text-grm-secondary mt-0.5">
            {__("Your complaint will be processed without contact information")}
          </span>
        </button>

        <button
          type="button"
          aria-pressed={form.contactMedium === "updates"}
          onClick={() => setField("contactMedium", "updates")}
          className={`w-full min-h-[44px] text-left p-3 rounded-lg border transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
            form.contactMedium === "updates"
              ? "border-primary-700 bg-primary-50"
              : "border-grm-field hover:border-primary-700"
          }`}
        >
          <span className="text-sm font-medium text-gray-900">
            {__("I want updates")}
          </span>
          <span className="block text-sm text-grm-secondary mt-0.5">
            {__("Provide your contact details to receive status updates")}
          </span>
        </button>
      </div>

      {form.contactMedium === "updates" && (
        <div className="space-y-3 border-t border-gray-100 pt-4">
          <div>
            <label htmlFor="contact-phone" className="text-sm font-semibold text-gray-800 mb-1 block">
              {__("Phone Number")} *
            </label>
            <input
              id="contact-phone"
              name="phone"
              type="tel"
              required
              inputMode="tel"
              autoComplete="tel"
              value={form.phone}
              onChange={(e) => setField("phone", e.target.value)}
              placeholder="+250..."
              className="w-full min-h-[48px] p-2.5 border border-grm-field rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-primary-700"
            />
          </div>

          <fieldset>
            <legend className="text-sm font-semibold text-gray-800 mb-1 block">
              {__("Preferred Contact Method")}
            </legend>
            <div className="flex flex-wrap gap-2">
              {[
                { value: "phone_number", label: __("Phone") },
                { value: "email", label: __("Email") },
                { value: "whatsapp", label: "WhatsApp" },
              ].map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  aria-pressed={form.contactInfoType === opt.value}
                  onClick={() => setField("contactInfoType", opt.value)}
                  className={`min-h-[44px] px-4 rounded-lg border text-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
                    form.contactInfoType === opt.value
                      ? "border-primary-700 bg-primary-50 font-medium"
                      : "border-grm-field hover:border-primary-700"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </fieldset>

          {form.contactInfoType === "email" && (
            <div>
              <label htmlFor="contact-email" className="text-sm font-semibold text-gray-800 mb-1 block">
                {__("Email Address")}
              </label>
              <input
                id="contact-email"
                name="email"
                type="email"
                inputMode="email"
                autoComplete="email"
                value={form.contactInformation}
                onChange={(e) => setField("contactInformation", e.target.value)}
                placeholder="email@example.com"
                className="w-full min-h-[48px] p-2.5 border border-grm-field rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-primary-700"
              />
            </div>
          )}

          <div>
            <label htmlFor="citizen-name" className="text-sm font-semibold text-gray-800 mb-1 block">
              {__("Your Name")} ({__("optional")})
            </label>
            <input
              id="citizen-name"
              name="name"
              type="text"
              autoComplete="name"
              value={form.citizenName}
              onChange={(e) => setField("citizenName", e.target.value)}
              className="w-full min-h-[48px] p-2.5 border border-grm-field rounded-lg text-base focus:outline-none focus:ring-2 focus:ring-primary-700"
            />
          </div>

          <fieldset>
            <legend className="text-sm font-semibold text-gray-800 mb-1 block">
              {__("Gender")} ({__("optional")})
            </legend>
            <div className="flex flex-wrap gap-2">
              {[
                { value: "male", label: __("Male") },
                { value: "female", label: __("Female") },
                { value: "other", label: __("Other") },
              ].map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  aria-pressed={form.gender === opt.value}
                  onClick={() => setField("gender", opt.value)}
                  className={`min-h-[44px] px-4 rounded-lg border text-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 ${
                    form.gender === opt.value
                      ? "border-primary-700 bg-primary-50 font-medium"
                      : "border-grm-field hover:border-primary-700"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </fieldset>
        </div>
      )}
    </div>
  );

  const renderVerifyStep = () => (
    <div>
      <h2 className="text-lg font-bold text-gray-900 mb-1">{__("Verify & Submit")}</h2>
      <p className="text-sm text-grm-secondary mb-4">
        {__("Complete verification to submit your complaint")}
      </p>

      {config?.otp_enabled && form.contactMedium === "updates" && form.phone && (
        <div className="mb-4">
          {!otpSent ? (
            <button
              type="button"
              onClick={handleSendOtp}
              disabled={otpSending}
              className="w-full min-h-[48px] py-2.5 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm font-medium transition-all disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
            >
              {otpSending ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  {__("Sending...")}
                </span>
              ) : (
                __("Send verification code to {0}").replace("{0}", form.phone)
              )}
            </button>
          ) : (
            <div className="space-y-3">
              <label htmlFor="otp-code" className="block text-sm text-gray-800">
                {__("Enter the 6-digit code sent to {0}").replace("{0}", form.phone)}
              </label>
              <input
                id="otp-code"
                name="one-time-code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={form.otp}
                onChange={(e) => {
                  const val = e.target.value.replace(/\D/g, "").slice(0, 6);
                  setField("otp", val);
                }}
                placeholder="000000"
                maxLength={6}
                className="w-full min-h-[48px] p-2.5 border border-grm-field rounded-lg text-center text-lg font-mono tracking-[0.5em] focus:outline-none focus:ring-2 focus:ring-primary-700"
              />
              <button
                type="button"
                onClick={() => {
                  setOtpSent(false);
                  setField("otp", "");
                }}
                className="min-h-[44px] text-sm font-medium text-primary-800 underline"
              >
                {__("Resend code")}
              </button>
            </div>
          )}
        </div>
      )}

      {config?.turnstile_site_key && (
        <TurnstileWidget
          siteKey={config.turnstile_site_key}
          onToken={setTurnstileToken}
          __={__}
        />
      )}
    </div>
  );

  const renderResult = () => (
    <div className="text-center py-6">
      <div className="w-16 h-16 rounded-full bg-primary-100 flex items-center justify-center mx-auto mb-4">
        <CheckCircle className="w-8 h-8 text-primary-800" aria-hidden="true" />
      </div>

      <h2 className="text-lg font-bold text-gray-900 mb-2">
        {__("Complaint Submitted Successfully")}
      </h2>
      <p className="text-sm text-grm-secondary mb-6">
        {__("Save your tracking code to check the status of your complaint")}
      </p>

      <div className="bg-gray-50 rounded-xl p-4 mb-4 inline-block">
        <p className="text-sm text-grm-secondary mb-1">
          {__("Tracking Code")}
        </p>
        <div className="flex items-center gap-2">
          {/* No aria-labelledby here: a plain span has no role, so naming it
              is ignored by most screen readers and the label was lost. The
              "Tracking Code" paragraph sits immediately before it and is
              read in order, which is what a label is for. */}
          <span className="text-2xl font-bold font-mono text-gray-900 tracking-wider">
            {trackingCode}
          </span>
          <button
            type="button"
            onClick={copyCode}
            className="flex h-11 w-11 items-center justify-center rounded-lg hover:bg-gray-200 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
            aria-label={copied ? __("Copied") : __("Copy tracking code")}
          >
            {copied ? (
              <CheckCircle className="w-5 h-5 text-primary-800" aria-hidden="true" />
            ) : (
              <Copy className="w-5 h-5 text-grm-secondary" aria-hidden="true" />
            )}
          </button>
        </div>
        {/* Copying can be refused outright. Saying nothing would leave the
            user believing the code was on their clipboard when it was not. */}
        <p role="status" className="mt-2 text-sm text-grm-secondary">
          {copyFailed
            ? __("Copying is blocked in this browser -- please write the code down.")
            : copied
              ? __("Copied")
              : ""}
        </p>
      </div>

      <div className="flex flex-col gap-2 mt-6">
        {/* A plain href here reloaded the whole SPA to reach a route the
            router already owns -- a blank screen and a second download of
            every asset, on the one screen where the citizen is holding a
            code they must not lose. */}
        <Link
          to={`/grm-portal/track?code=${encodeURIComponent(trackingCode)}`}
          className="flex min-h-[48px] items-center justify-center py-2.5 bg-primary-700 hover:bg-primary-800 text-white rounded-lg text-sm font-medium no-underline transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-2"
        >
          {__("Track Your Complaint")}
        </Link>
        <button
          type="button"
          onClick={resetForm}
          className="min-h-[48px] py-2.5 border border-grm-field hover:bg-gray-50 rounded-lg text-sm text-gray-800 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
        >
          {__("Submit Another Complaint")}
        </button>
      </div>
    </div>
  );

  // --- Step router ---
  const renderCurrentStep = () => {
    // Keyed off the tracking code, not the step: now that the step lives in
    // the URL, Back from the confirmation would otherwise return the user to
    // a live Submit button for a complaint already filed.
    if (trackingCode) return renderResult();
    switch (stepKey) {
      case "project":
        return renderProjectStep();
      case "category":
        return renderCategoryStep();
      case "region":
        return renderRegionStep();
      case "describe":
        return renderDescribeStep();
      case "contact":
        return renderContactStep();
      case "verify":
        return renderVerifyStep();
      default:
        return null;
    }
  };

  const hint = stepHint(stepKey);

  // Changing step swaps the whole panel without a navigation, so nothing
  // moves focus or the scroll position on its own: a screen reader stayed on
  // the button that had just vanished, and on a phone the next step opened
  // scrolled to wherever the last one ended. Focusing the panel puts the
  // reader at its heading and the viewport at the top of the form.
  const stepRegionRef = useRef<HTMLDivElement>(null);
  const firstRender = useRef(true);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    stepRegionRef.current?.focus();
    window.scrollTo(0, 0);
  }, [stepKey, trackingCode]);

  // Back out of the confirmation, not into it. The result card renders on the
  // strength of the tracking code alone, so the device Back button changed the
  // URL underneath an unchanged screen -- on a phone that reads as a dead
  // button, and the citizen presses it until the browser leaves the site. The
  // complaint is filed and the draft is cleared, so there is no earlier step
  // left to return to; the portal home is the honest destination.
  useEffect(() => {
    if (!trackingCode) return;
    const onPop = () => navigate("/grm-portal", { replace: true });
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, [trackingCode, navigate]);

  // A submission that fails has to be seen. The alert renders above the step
  // card, which on the taller steps is a screenful above the button that was
  // just pressed, so nothing appeared to happen and the citizen pressed it
  // again. Moving focus carries both the viewport and the screen reader.
  const errorRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!error) return;
    const node = errorRef.current;
    if (!node) return;
    const reduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    node.scrollIntoView({ block: "center", behavior: reduced ? "auto" : "smooth" });
    node.focus();
  }, [error]);

  return (
    <div className="max-w-lg mx-auto px-4 py-8">
      <div className="text-center mb-4">
        <h1 className="text-xl font-bold text-gray-900 mb-1">
          {__("Submit a Grievance")}
        </h1>
        {!trackingCode && (
          <p className="text-sm text-grm-secondary">
            {__("Step {0}").replace("{0}", String(stepIndex))}
            {stepCountKnown && ` / ${totalVisibleSteps}`}
          </p>
        )}
      </div>

      {!trackingCode && (
        <ProgressDots
          current={stepIndex}
          // Assume the region step exists while unknown — most projects define
          // regions, so the dot count stays put in the common case instead of
          // growing under the user.
          total={stepCountKnown ? totalVisibleSteps : totalVisibleSteps + 1}
          indeterminate={!stepCountKnown}
        />
      )}

      {/* The project was decided for the user, so state it plainly rather than
          leaving them to wonder what this complaint is being filed against.
          Only offer "Change" when there is genuinely something else to pick. */}
      {projectLocked && selectedProject && !trackingCode && (
        <div className="mb-4 flex items-center gap-2 rounded-lg border border-gray-200 bg-gray-50 px-3 py-2">
          <FolderOpen className="w-4 h-4 text-primary-700 shrink-0" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <span className="block text-sm text-grm-secondary">
              {__("Project")}
            </span>
            <span className="block text-sm font-medium text-gray-900 truncate">
              {selectedProject.title}
            </span>
          </div>
          {projects.length > 1 && (
            <button
              onClick={() => {
                setProjectLocked(false);
                setStep(1);
              }}
              type="button"
              className="min-h-[44px] px-2 text-sm font-semibold text-primary-800 underline shrink-0"
            >
              {__("Change")}
            </button>
          )}
        </div>
      )}

      {error && (
        <div
          ref={errorRef}
          tabIndex={-1}
          role="alert"
          className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-700"
        >
          <AlertCircle className="w-4 h-4 text-red-700 mt-0.5 flex-shrink-0" aria-hidden="true" />
          <span className="text-sm font-medium text-red-700">{error}</span>
        </div>
      )}

      {/* Each step is a real form. Without one, Enter in a text field did
          nothing -- the habit of typing an answer and pressing Enter simply
          failed, on a wizard that is six fields deep. */}
      <form onSubmit={handleStepSubmit} noValidate>
      <div
        ref={stepRegionRef}
        tabIndex={-1}
        className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
      >
        {renderCurrentStep()}
      </div>

      {!trackingCode && (
        <>
          <div className="flex gap-3 mt-4">
            {stepIndex > 1 && (
              <button
                type="button"
                onClick={prevStep}
                className="flex min-h-[48px] items-center gap-1 px-4 py-2.5 border border-grm-field hover:bg-gray-50 rounded-lg text-sm text-gray-800 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
              >
                <ChevronLeft className="w-4 h-4" aria-hidden="true" />
                {__("Back")}
              </button>
            )}

            {/* aria-disabled, not disabled. A disabled button cannot be
                focused, so the hint tied to it with aria-describedby was
                unreachable: the one explanation of why the button would not
                work could never be read out. */}
            {!isLastStep && (
              <button
                type="submit"
                aria-disabled={!isStepValid(stepKey)}
                aria-describedby={hint ? "step-hint" : undefined}
                className="flex-1 flex min-h-[48px] items-center justify-center gap-1 px-4 py-2.5 bg-primary-700 hover:bg-primary-800 text-white rounded-lg text-sm font-medium transition-all aria-disabled:bg-gray-600 aria-disabled:hover:bg-gray-600 aria-disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-2"
              >
                {__("Next")}
                <ChevronRight className="w-4 h-4" aria-hidden="true" />
              </button>
            )}

            {/* One Submit button, owned by the footer. The verify step used to
                render a second one of its own, so the last step showed two. */}
            {isLastStep && (
              <button
                type="submit"
                aria-disabled={submitting || !isStepValid(stepKey)}
                aria-describedby={hint ? "step-hint" : undefined}
                className="flex-1 min-h-[48px] py-2.5 bg-primary-700 hover:bg-primary-800 text-white rounded-lg text-sm font-semibold transition-all aria-disabled:bg-gray-600 aria-disabled:hover:bg-gray-600 aria-disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-700 focus-visible:ring-offset-2"
              >
                {submitting ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                    {__("Submitting...")}
                  </span>
                ) : (
                  __("Submit Complaint")
                )}
              </button>
            )}
          </div>

          {/* Say what is still missing rather than greying the button out and
              leaving the user to guess which field it is waiting on. The
              paragraph stays mounted: a live region that appears along with
              its text is not announced by most screen readers. */}
          <p
            id="step-hint"
            aria-live="polite"
            className={hint ? "mt-2 text-sm text-grm-secondary" : "sr-only"}
          >
            {hint}
          </p>
        </>
      )}
      </form>
    </div>
  );
}
