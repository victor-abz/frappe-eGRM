import { Smartphone, User, Phone, Home } from "lucide-react";
import { useTranslate } from "@/hooks/useTranslate";

const methods = [
  {
    title: "Mobile App",
    description: "Submit through the GRM mobile application available on Android",
    icon: Smartphone,
    iconBg: "bg-blue-100",
    iconColor: "text-blue-600",
    borderColor: "border-blue-200",
  },
  {
    title: "Field Officer",
    description: "Contact a field officer who can register your complaint on your behalf",
    icon: User,
    iconBg: "bg-purple-100",
    iconColor: "text-purple-600",
    borderColor: "border-purple-200",
  },
  {
    title: "Phone Hotline",
    description: "Call the GRM hotline to submit your grievance by phone",
    icon: Phone,
    iconBg: "bg-emerald-100",
    iconColor: "text-emerald-600",
    borderColor: "border-emerald-200",
  },
  {
    title: "In Person",
    description: "Visit the nearest GRM office to submit your complaint in person",
    icon: Home,
    iconBg: "bg-amber-100",
    iconColor: "text-amber-600",
    borderColor: "border-amber-200",
  },
];

export default function SubmitPage() {
  const { __ } = useTranslate();

  return (
    <div className="max-w-2xl mx-auto px-4 py-12">
      <div className="text-center mb-8">
        <h1 className="text-xl font-bold text-gray-900 mb-1">{__("Submit a Grievance")}</h1>
        <p className="text-sm text-grm-muted">{__("Choose a method to file your complaint")}</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {methods.map((method) => (
          <div
            key={method.title}
            className={`bg-white rounded-xl p-5 border ${method.borderColor} hover:shadow-md transition-all duration-200`}
          >
            <div className={`w-10 h-10 rounded-lg ${method.iconBg} flex items-center justify-center mb-3`}>
              <method.icon className={`w-5 h-5 ${method.iconColor}`} />
            </div>
            <h3 className="text-sm font-bold text-gray-900 mb-1">{__(method.title)}</h3>
            <p className="text-xs text-gray-500 leading-relaxed">{__(method.description)}</p>
          </div>
        ))}
      </div>

      <p className="text-center text-xs text-grm-muted mt-8">
        {__("Web form coming soon. For now, please use one of the methods above.")}
      </p>
    </div>
  );
}
