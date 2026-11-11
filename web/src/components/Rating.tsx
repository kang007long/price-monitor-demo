import { StarIcon } from "./Icons";

export function Rating({ value }: { value: number | null }) {
  const rating = value ?? 0;
  return (
    <span
      className="rating"
      aria-label={value ? `${value} out of 5 stars` : "No rating"}
      title={value ? `${value} / 5` : "No rating"}
    >
      {[1, 2, 3, 4, 5].map((star) => (
        <StarIcon key={star} className={star <= rating ? "" : "star-empty"} />
      ))}
    </span>
  );
}
