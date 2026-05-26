import type { Meta, StoryObj } from "@storybook/react-vite";

import { StudyCard } from "~/lib/merism";

const meta: Meta<typeof StudyCard> = {
  title: "patterns/StudyCard",
  component: StudyCard,
  parameters: {
    docs: {
      description: {
        component:
          "Card for the Studies list. Shows name, research goal, status dot, and a recruited count.",
      },
    },
  },
  args: {
    onOpen: (id: string) => console.log("open", id),
  },
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Draft: Story = {
  args: {
    id: "b3f12a9d",
    name: "Power user churn — day 14 cohort",
    researchGoal:
      "Understand the usage patterns and psychological friction points that drive advanced users to cancel in the second week.",
    status: "draft",
  },
};

export const Recruiting: Story = {
  args: {
    id: "9d7c2441",
    name: "Onboarding — first 5 minutes",
    researchGoal:
      "What do new users do in their first 5 minutes, and where do the 'aha' vs 'abandon' signals diverge?",
    status: "recruiting",
    completedCount: 4,
  },
};

export const Active: Story = {
  args: {
    id: "22c4f001",
    name: "Pricing page — framework pilot",
    researchGoal:
      "Did participants understand the pricing tiers, and which tier did they identify with?",
    status: "active",
    completedCount: 12,
  },
};

export const Grid: Story = {
  render: () => (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <StudyCard
        id="a"
        name="Power user churn"
        researchGoal="Why do advanced users cancel in week 2?"
        status="draft"
        onOpen={() => {}}
      />
      <StudyCard
        id="b"
        name="Onboarding friction"
        researchGoal="Where do new users abandon in their first 5 minutes?"
        status="recruiting"
        completedCount={4}
        onOpen={() => {}}
      />
    </div>
  ),
};
