import type { Block } from "@/lib/schema";

type FormProps = Extract<Block, { type: "form" }>;

/** Forms are documented, not functional: wire them to your own backend during the redesign. */
export default function FormBlock({ fields, submitLabel }: FormProps) {
  return (
    <form className="grid max-w-xl gap-4 rounded-card border border-line p-6" aria-describedby="form-hint">
      {fields.map((field) => {
        const id = `field-${field.name}`;
        const label = (
          <label htmlFor={id} className="text-sm font-medium">
            {field.label || field.name}
            {field.required ? " *" : ""}
          </label>
        );
        const common = { id, name: field.name, required: field.required, placeholder: field.placeholder ?? undefined, className: "w-full rounded-md border border-line px-3 py-2" };
        if (field.inputType === "textarea") return <div key={field.name} className="grid gap-1">{label}<textarea rows={5} {...common} /></div>;
        if (field.inputType === "select") {
          return (
            <div key={field.name} className="grid gap-1">
              {label}
              <select {...common}>
                {(field.options ?? []).map((option) => (
                  <option key={option}>{option}</option>
                ))}
              </select>
            </div>
          );
        }
        if (field.inputType === "checkbox" || field.inputType === "radio") {
          return (
            <label key={field.name} className="flex items-center gap-2 text-sm">
              <input type={field.inputType} id={id} name={field.name} required={field.required} /> {field.label || field.name}
            </label>
          );
        }
        return <div key={field.name} className="grid gap-1">{label}<input type={field.inputType} {...common} /></div>;
      })}
      <button type="button" disabled className="btn btn-primary w-fit cursor-not-allowed opacity-60">
        {submitLabel || "Absenden"}
      </button>
      <p id="form-hint" className="text-xs text-muted">
        Prototyp: Dieses Formular ist noch nicht angebunden.
      </p>
    </form>
  );
}
