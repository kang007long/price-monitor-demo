import { coverPalette, initials } from "@/lib/cover";

export function BookCover({
  title,
  size = "small",
}: {
  title: string;
  size?: "small" | "large";
}) {
  const palette = coverPalette(title);
  return (
    <span
      className={`book-cover${size === "large" ? " large" : ""}`}
      style={palette}
      aria-hidden="true"
    >
      {initials(title)}
    </span>
  );
}
