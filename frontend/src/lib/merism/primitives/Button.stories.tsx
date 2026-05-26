import type { Meta, StoryObj } from "@storybook/react-vite";
import { ArrowRight, Plus, Sparkles, Trash2 } from "lucide-react";

import { Button } from "~/lib/merism";

const meta: Meta<typeof Button> = {
  title: "primitives/Button",
  component: Button,
  argTypes: {
    variant: {
      control: "select",
      options: ["primary", "secondary", "ghost", "danger", "link"],
    },
    size: {
      control: "select",
      options: ["sm", "md", "lg", "icon"],
    },
  },
};

export default meta;
type Story = StoryObj<typeof meta>;

export const Primary: Story = {
  args: { children: "Launch study", variant: "primary" },
};

export const Secondary: Story = {
  args: { children: "Edit brief", variant: "secondary" },
};

export const Ghost: Story = {
  args: { children: "Cancel", variant: "ghost" },
};

export const Danger: Story = {
  args: {
    children: "Delete",
    variant: "danger",
    iconLeft: <Trash2 className="h-4 w-4" />,
  },
};

export const Link: Story = {
  args: { children: "View all sessions →", variant: "link" },
};

export const WithLeftIcon: Story = {
  args: {
    children: "New study",
    iconLeft: <Plus className="h-4 w-4" />,
  },
};

export const WithRightIcon: Story = {
  args: {
    children: "Continue",
    iconRight: <ArrowRight className="h-4 w-4" />,
  },
};

export const Loading: Story = {
  args: {
    children: "Saving",
    isLoading: true,
  },
};

export const Disabled: Story = {
  args: {
    children: "Unavailable",
    disabled: true,
  },
};

export const SizeLadder: Story = {
  render: () => (
    <div className="flex items-center gap-3">
      <Button size="sm" iconLeft={<Sparkles className="h-4 w-4" />}>
        Small
      </Button>
      <Button size="md" iconLeft={<Sparkles className="h-4 w-4" />}>
        Medium
      </Button>
      <Button size="lg" iconLeft={<Sparkles className="h-4 w-4" />}>
        Large
      </Button>
    </div>
  ),
};

export const AllVariants: Story = {
  render: () => (
    <div className="flex flex-wrap items-center gap-3">
      <Button variant="primary">Primary</Button>
      <Button variant="secondary">Secondary</Button>
      <Button variant="ghost">Ghost</Button>
      <Button variant="danger">Danger</Button>
      <Button variant="link">Link</Button>
    </div>
  ),
};
