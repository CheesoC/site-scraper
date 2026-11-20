import type { Block } from "@/lib/schema";
import Card from "./Card";

type CardBlock = Extract<Block, { type: "card" }>;

export default function CardGrid({ cards }: { cards: CardBlock[] }) {
  const columns = cards.length % 3 === 0 || cards.length > 4 ? "lg:grid-cols-3" : "lg:grid-cols-2";
  return (
    <div className={`grid gap-6 sm:grid-cols-2 ${columns}`}>
      {cards.map((card, index) => (
        <Card key={index} blocks={card.blocks} link={card.link} />
      ))}
    </div>
  );
}
