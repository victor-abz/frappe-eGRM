import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import {
  ShieldCheck,
  BarChart3,
  Search,
  FileText,
  ArrowRight,
  FolderOpen,
  Send,
  Eye,
  CheckCircle,
} from "lucide-react";
import { useHomeListings } from "@/hooks/useProjects";
import { useTranslate } from "@/hooks/useTranslate";
import { usePortalConfig } from "@/hooks/usePortalConfig";
import { stripHtml } from "@/utils";

type Action = {
  title: string;
  description: string;
  /** The button names the next action — an arrow alone says nothing on touch. */
  cta: string;
  icon: typeof Send;
  to: string;
  bgColor: string;
  iconColor: string;
  btnColor: string;
  borderColor: string;
  gate?: "dashboard" | "reports";
};

const ALL_ACTIONS: Action[] = [
  {
    title: "Raise Issue",
    description: "File a new grievance",
    cta: "Start form",
    icon: Send,
    to: "/grm-portal/submit",
    bgColor: "bg-rose-50",
    iconColor: "text-rose-600",
    btnColor: "bg-rose-600 hover:bg-rose-700",
    borderColor: "border-rose-100",
  },
  {
    title: "Track Complaint",
    description: "Check your status",
    cta: "Enter code",
    icon: Search,
    to: "/grm-portal/track",
    bgColor: "bg-amber-50",
    iconColor: "text-amber-600",
    btnColor: "bg-amber-700 hover:bg-amber-800",
    borderColor: "border-amber-100",
  },
  {
    title: "View Reports",
    description: "Download public reports",
    cta: "Browse reports",
    icon: FileText,
    to: "/grm-portal/reports",
    bgColor: "bg-primary-50",
    iconColor: "text-primary-600",
    btnColor: "bg-primary-700 hover:bg-primary-800",
    borderColor: "border-primary-100",
    gate: "reports",
  },
  {
    title: "Dashboard",
    description: "See public statistics",
    cta: "Open dashboard",
    icon: BarChart3,
    to: "/grm-portal/dashboard",
    bgColor: "bg-blue-50",
    iconColor: "text-blue-600",
    btnColor: "bg-blue-600 hover:bg-blue-700",
    borderColor: "border-blue-100",
    gate: "dashboard",
  },
];

const processSteps = [
  { title: "Submit", description: "File your grievance via web, mobile, or field officer", icon: Send, iconColor: "text-blue-600", bg: "bg-blue-50", ring: "ring-blue-200" },
  { title: "Track", description: "Get a tracking code and monitor progress", icon: Eye, iconColor: "text-purple-600", bg: "bg-purple-50", ring: "ring-purple-200" },
  { title: "Resolve", description: "Solution proposed, implemented, and verified", icon: CheckCircle, iconColor: "text-primary-700", bg: "bg-primary-50", ring: "ring-primary-200" },
];

// The icon tile carries each project's colour; a thick side border was doing
// the same job twice and cost 4px of an already narrow phone row.
const projectColors = [
  { iconBg: "bg-indigo-100", iconColor: "text-indigo-600" },
  { iconBg: "bg-rose-100", iconColor: "text-rose-600" },
  { iconBg: "bg-cyan-100", iconColor: "text-cyan-600" },
  { iconBg: "bg-violet-100", iconColor: "text-violet-600" },
  { iconBg: "bg-amber-100", iconColor: "text-amber-600" },
  { iconBg: "bg-primary-100", iconColor: "text-primary-600" },
  { iconBg: "bg-sky-100", iconColor: "text-sky-600" },
  { iconBg: "bg-red-100", iconColor: "text-red-600" },
];

export default function HomePage() {
  const { __ } = useTranslate();
  const { config } = usePortalConfig();
  const { projects, isLoading: projectsLoading, error: projectsError } = useHomeListings();

  const actions = ALL_ACTIONS.filter((action) => {
    if (action.gate === "dashboard") return config.show_dashboard;
    if (action.gate === "reports") return config.show_reports;
    return true;
  });

  const [searchQuery, setSearchQuery] = useState("");

  const filteredProjects = useMemo(() => {
    if (!projects) return [];
    const needle = searchQuery.trim().toLowerCase();
    if (!needle) return projects;
    return projects.filter(
      (project) =>
        project.title.toLowerCase().includes(needle) ||
        stripHtml(project.description).toLowerCase().includes(needle),
    );
  }, [projects, searchQuery]);

  return (
    <div>
      {/* Hero — compact */}
      {/* The gradient used to start at primary-500, where white text measures
          2.27:1 -- the headline was unreadable at exactly the end of the band
          a phone shows first. From 800 to 900 both ends clear AA. */}
      <section className="w-full bg-gradient-to-br from-primary-800 to-primary-900 text-white py-6 px-4 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-36 h-36 bg-white/10 rounded-full -translate-x-1/2 -translate-y-1/2 blur-2xl" />
        <div className="absolute bottom-0 right-0 w-48 h-48 bg-primary-400/20 rounded-full translate-x-1/3 translate-y-1/3 blur-2xl" />
        <div className="max-w-7xl mx-auto flex items-center gap-4 relative z-10">
          <div className="bg-white/20 p-3 rounded-full backdrop-blur-sm border border-white/30 shrink-0">
            <ShieldCheck className="w-8 h-8 text-white" strokeWidth={1.5} aria-hidden="true" />
          </div>
          <div className="flex-1">
            <h1 className="text-xl md:text-2xl font-bold tracking-tight">
              {__("Grievance Redress")}
            </h1>
            <p className="text-sm text-primary-50 font-medium mt-0.5">
              {__("We are here to help. Track complaints, view statistics, and submit new grievances easily.")}
            </p>
          </div>
        </div>
      </section>

      {/* Action Cards — centered, wrap gracefully when fewer are enabled */}
      <section className="py-8 px-4 -mt-4 relative z-20">
        <div className="max-w-7xl mx-auto">
          {/* Phones stack these full width: side-by-side halves squeezed the
              labels, and the row layout keeps each card one thumb tall. */}
          <div className="flex flex-col sm:flex-row sm:flex-wrap sm:justify-center gap-3 sm:gap-4">
            {actions.map((action) => (
              <Link
                key={action.title}
                to={action.to}
                className={`${action.bgColor} rounded-xl p-3 sm:p-4 shadow-lg hover:shadow-xl transition-all duration-300 sm:transform sm:hover:-translate-y-1 border ${action.borderColor} flex items-center gap-2.5 sm:gap-0 sm:flex-col sm:items-center sm:text-center no-underline sm:basis-60 lg:basis-64 sm:max-w-xs`}
              >
                <div className={`w-11 h-11 shrink-0 rounded-full bg-white shadow-md flex items-center justify-center sm:mb-2.5 ${action.iconColor}`}>
                  <action.icon className="w-5 h-5" strokeWidth={2} aria-hidden="true" />
                </div>
                <div className="min-w-0 flex-1 sm:flex sm:flex-col sm:flex-1">
                  <h2 className="text-sm font-bold text-gray-900 mb-0.5">{__(action.title)}</h2>
                  <p className="text-sm text-gray-700 sm:mb-3 sm:flex-grow">{__(action.description)}</p>
                </div>
                <span className={`shrink-0 min-h-[44px] py-2 px-3 rounded-lg text-white font-semibold text-sm shadow-sm flex items-center justify-center gap-1.5 sm:w-full ${action.btnColor}`}>
                  <span>{__(action.cta)}</span>
                  <ArrowRight className="w-4 h-4 shrink-0" aria-hidden="true" />
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Projects — a screen-reader-only heading over search + grid.
          Hidden entirely when there is nothing to choose between: with a
          single project the search box and one-card grid are all noise, and
          "Raise Issue" already lands on that project.
          There was a second control here, "All Categories", listing issue
          categories while the list beneath it holds projects. Projects carry
          no category, so the filter could never match anything and silently
          did nothing. Removed rather than wired up: the two are unrelated. */}
      {(projectsLoading || projects.length > 1) && (
      <section className="py-8 px-4 bg-gray-50" aria-labelledby="projects-heading">
        <div className="max-w-7xl mx-auto">
          {/* Named, but only for assistive tech. The section is obvious on
              screen -- a search box over a grid of project cards -- yet
              without a heading its cards' h3s hung off the quick-action
              cards above, and the section itself was unreachable from a
              screen reader's list of landmarks and headings. */}
          <h2 id="projects-heading" className="sr-only">{__("Projects")}</h2>
          <div className="flex flex-col sm:flex-row gap-3 mb-5">
            <div className="relative flex-1 max-w-sm">
              <label htmlFor="project-search" className="sr-only">
                {__("Search projects")}
              </label>
              <Search
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500"
                aria-hidden="true"
              />
              <input
                id="project-search"
                name="project-search"
                type="search"
                placeholder={__("Search projects...")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full h-12 pl-9 pr-3 text-base bg-white border border-grm-field rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-700 focus:border-transparent placeholder:text-gray-500"
              />
            </div>
          </div>

          {/* Placeholders built from the card's own box -- same padding,
              border, icon square and three text lines -- so the real grid
              lands at the height the skeleton already reserved. A single
              hard-coded height could only be right for one description
              length, and the grid used to appear from nothing anyway,
              shoving everything below it down the page mid-read. */}
          {projectsLoading && (
            <div
              className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3"
              aria-hidden="true"
            >
              {[0, 1, 2].map((n) => (
                <div
                  key={n}
                  className="flex min-h-[48px] animate-pulse items-center gap-3 rounded-lg border border-grm-border bg-white p-3 shadow-sm"
                >
                  <div className="h-9 w-9 shrink-0 rounded-lg bg-gray-200" />
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="h-5 w-2/3 rounded bg-gray-200" />
                    <div className="h-5 w-full rounded bg-gray-100" />
                    <div className="h-5 w-1/3 rounded bg-gray-100" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {!projectsLoading && Boolean(projectsError) && (
            <p role="alert" className="py-8 text-center text-sm font-medium text-red-700">
              {__("Could not load the list of projects. Check your connection and reload the page.")}
            </p>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredProjects.map((project, idx) => {
              const color = projectColors[idx % projectColors.length];
              // No aria-label on the card. One here replaced everything
              // inside it, so a screen reader heard the project's title and
              // never the description a sighted visitor uses to pick between
              // projects. The card's own text is the better name.
              return (
                <Link
                  key={project.name}
                  to={`/grm-portal/submit?project=${encodeURIComponent(project.name)}`}
                  className="group bg-white rounded-lg p-3 shadow-sm border border-grm-border hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 flex min-h-[48px] items-center gap-3 no-underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-700"
                >
                  <div className={`p-2 rounded-lg ${color.iconBg} shrink-0`}>
                    <FolderOpen className={`w-5 h-5 ${color.iconColor}`} aria-hidden="true" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-gray-900 truncate">{project.title}</h3>
                    <p className="text-gray-600 text-sm line-clamp-2">{stripHtml(project.description)}</p>
                    {/* Touch has no hover: on phones the hint stays visible rather
                        than sitting invisible while still taking up its line. */}
                    <span className="text-sm font-semibold text-primary-800 lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-visible:opacity-100 transition-opacity">
                      {__("Raise Issue")}
                    </span>
                  </div>
                  <ArrowRight
                    className="w-4 h-4 text-gray-500 group-hover:text-primary-800 group-hover:translate-x-0.5 transition-all shrink-0"
                    aria-hidden="true"
                  />
                </Link>
              );
            })}
          </div>

          {/* Typing in the search box silently rebuilds the grid below it.
              Someone who cannot see that grid got no signal that anything
              had happened, let alone how much was left -- so the count is
              said out loud. Only while a query is active: on an untouched
              page the grid is simply the list, not a result. */}
          <div className="sr-only" role="status" aria-live="polite">
            {!projectsLoading && !projectsError && searchQuery.trim()
              ? __("{0} projects found", [String(filteredProjects.length)])
              : ""}
          </div>

          {!projectsLoading && !projectsError && filteredProjects.length === 0 && (
            <div className="text-center py-12 text-grm-secondary">
              <Search className="w-8 h-8 mx-auto mb-2 text-gray-500" aria-hidden="true" />
              <p className="text-sm">{__("No projects found")}</p>
            </div>
          )}
        </div>
      </section>
      )}

      {/* How It Works — horizontal on lg */}
      <section className="py-10 px-4 bg-white">
        <div className="max-w-4xl mx-auto">
          <h2 className="text-lg font-bold text-center text-gray-900 mb-8">
            {__("How It Works")}
          </h2>
          <div className="flex flex-col lg:flex-row lg:items-start lg:gap-0 gap-4">
            {processSteps.map((step, index) => (
              <div key={step.title} className="flex flex-col lg:flex-row lg:items-start lg:flex-1">
                {/* Step content */}
                <div className="flex items-start gap-3 lg:flex-col lg:items-center lg:text-center flex-1">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${step.bg} ring-2 ${step.ring} shadow-sm shrink-0`}>
                    <step.icon className={`w-5 h-5 ${step.iconColor}`} strokeWidth={2} aria-hidden="true" />
                  </div>
                  <div className="lg:mt-3">
                    <span className="text-xs font-bold uppercase tracking-wider text-grm-secondary">
                      {__("Step {0}", [String(index + 1)])}
                    </span>
                    <h3 className="text-sm font-bold text-gray-900 leading-tight">{__(step.title)}</h3>
                    <p className="text-sm text-gray-600 mt-0.5 leading-relaxed max-w-[220px] lg:mx-auto">{__(step.description)}</p>
                  </div>
                </div>
                {/* Connector arrow */}
                {index < processSteps.length - 1 && (
                  <div className="hidden lg:flex items-center justify-center px-3 pt-5 shrink-0">
                    <ArrowRight className="w-4 h-4 text-gray-500" aria-hidden="true" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
