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
    btnColor: "bg-amber-600 hover:bg-amber-700",
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
    btnColor: "bg-primary-600 hover:bg-primary-700",
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
  { title: "Resolve", description: "Solution proposed, implemented, and verified", icon: CheckCircle, iconColor: "text-primary-600", bg: "bg-primary-50", ring: "ring-primary-200" },
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
  const { projects, categories } = useHomeListings();

  const actions = ALL_ACTIONS.filter((action) => {
    if (action.gate === "dashboard") return config.show_dashboard;
    if (action.gate === "reports") return config.show_reports;
    return true;
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [activeCategory, setActiveCategory] = useState("All");

  const filteredProjects = useMemo(() => {
    if (!projects) return [];
    return projects.filter((project) => {
      const desc = stripHtml(project.description);
      const matchesSearch =
        searchQuery === "" ||
        project.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        desc.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesCategory = activeCategory === "All" || activeCategory === "";
      return matchesSearch && matchesCategory;
    });
  }, [projects, searchQuery, activeCategory]);

  return (
    <div>
      {/* Hero — compact */}
      <section className="w-full bg-gradient-to-br from-primary-500 to-primary-800 text-white py-6 px-4 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-36 h-36 bg-white/10 rounded-full -translate-x-1/2 -translate-y-1/2 blur-2xl" />
        <div className="absolute bottom-0 right-0 w-48 h-48 bg-primary-400/20 rounded-full translate-x-1/3 translate-y-1/3 blur-2xl" />
        <div className="max-w-7xl mx-auto flex items-center gap-4 relative z-10">
          <div className="bg-white/20 p-3 rounded-full backdrop-blur-sm border border-white/30 shrink-0">
            <ShieldCheck className="w-8 h-8 text-white" strokeWidth={1.5} />
          </div>
          <div className="flex-1">
            <h1 className="text-xl md:text-2xl font-bold tracking-tight">
              {__("Grievance Redress")}
            </h1>
            <p className="text-sm text-primary-100 font-medium mt-0.5">
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
                  <action.icon className="w-5 h-5" strokeWidth={2} />
                </div>
                <div className="min-w-0 flex-1 sm:flex sm:flex-col sm:flex-1">
                  <h2 className="text-sm font-bold text-gray-900 mb-0.5">{__(action.title)}</h2>
                  <p className="text-[11px] text-gray-600 sm:mb-3 sm:flex-grow">{__(action.description)}</p>
                </div>
                <span className={`shrink-0 min-h-[44px] py-2 px-2.5 sm:px-3 rounded-lg text-white font-semibold text-xs shadow-sm flex items-center justify-center gap-1 sm:gap-1.5 sm:w-full ${action.btnColor}`}>
                  <span>{__(action.cta)}</span>
                  <ArrowRight className="w-3.5 h-3.5 shrink-0" />
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* Projects — no heading, just search + grid.
          Hidden entirely when there is nothing to choose between: with a
          single project the search box, category filter and one-card grid are
          all noise, and "Raise Issue" already lands on that project. */}
      {projects.length > 1 && (
      <section className="py-8 px-4 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <div className="flex flex-col sm:flex-row gap-3 mb-5">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder={__("Search projects...")}
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full h-11 pl-9 pr-3 text-sm bg-white border border-gray-200 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent placeholder:text-gray-400"
              />
            </div>
            <select
              value={activeCategory}
              onChange={(e) => setActiveCategory(e.target.value)}
              className="h-11 px-3 text-xs font-medium bg-white border border-gray-200 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              <option value="All">{__("All Categories")}</option>
              {categories?.map((cat) => (
                <option key={cat.name} value={cat.name}>
                  {__(cat.category_name)}
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {filteredProjects.map((project, idx) => {
              const color = projectColors[idx % projectColors.length];
              return (
                <Link
                  key={project.name}
                  to={`/grm-portal/submit?project=${encodeURIComponent(project.name)}`}
                  aria-label={__("Raise an issue about {0}", [project.title])}
                  className="group bg-white rounded-lg p-3 shadow-sm border border-gray-100 hover:shadow-md hover:-translate-y-0.5 transition-all duration-200 flex items-center gap-3 no-underline focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500"
                >
                  <div className={`p-2 rounded-lg ${color.iconBg} shrink-0`}>
                    <FolderOpen className={`w-5 h-5 ${color.iconColor}`} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-gray-900 truncate">{project.title}</h3>
                    <p className="text-gray-500 text-xs line-clamp-2">{stripHtml(project.description)}</p>
                    {/* Touch has no hover: on phones the hint stays visible rather
                        than sitting invisible while still taking up its line. */}
                    <span className="text-[11px] font-semibold text-primary-600 lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-visible:opacity-100 transition-opacity">
                      {__("Raise Issue")}
                    </span>
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-300 group-hover:text-primary-600 group-hover:translate-x-0.5 transition-all shrink-0" />
                </Link>
              );
            })}
          </div>

          {filteredProjects.length === 0 && (
            <div className="text-center py-12 text-gray-400">
              <Search className="w-8 h-8 mx-auto mb-2 opacity-50" />
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
                    <step.icon className={`w-5 h-5 ${step.iconColor}`} strokeWidth={2} />
                  </div>
                  <div className="lg:mt-3">
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${step.iconColor}`}>
                      {__("Step {0}", [String(index + 1)])}
                    </span>
                    <h3 className="text-sm font-bold text-gray-900 leading-tight">{__(step.title)}</h3>
                    <p className="text-xs text-gray-500 mt-0.5 leading-relaxed max-w-[200px] lg:mx-auto">{__(step.description)}</p>
                  </div>
                </div>
                {/* Connector arrow */}
                {index < processSteps.length - 1 && (
                  <div className="hidden lg:flex items-center justify-center px-3 pt-5 shrink-0">
                    <ArrowRight className="w-4 h-4 text-gray-300" />
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
