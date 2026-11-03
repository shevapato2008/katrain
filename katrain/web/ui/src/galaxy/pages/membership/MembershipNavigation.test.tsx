import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getGalaxyNavigation } from "../../components/layout/galaxyNavigation";
import GalaxyBottomNav from "../../components/layout/GalaxyBottomNav";

const requestNavigation = vi.hoisted(() => vi.fn());
vi.mock("../../context/GameNavigationContext", () => ({
  useGameNavigation: () => ({ requestNavigation }),
}));
vi.mock("../../../hooks/useTranslation", () => ({
  useTranslation: () => ({ t: (_: string, fallback: string) => fallback }),
}));
beforeEach(() => vi.clearAllMocks());
describe("membership navigation", () => {
  it("adds the membership destination to the shared sidebar navigation", () => {
    const translate = vi.fn((_, fallback) => fallback);
    expect(
      getGalaxyNavigation(translate).find(
        (item) => item.key === "membership",
      )?.path,
    ).toBe("/galaxy/membership");
    expect(translate).toHaveBeenCalledWith("membership:galaxy_title", "会员与用量");
  });
  it("keeps membership in More without adding another mobile destination", () => {
    render(
      <MemoryRouter
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <GalaxyBottomNav />
      </MemoryRouter>,
    );
    expect(
      screen.queryByRole("button", { name: "会员与用量" }),
    ).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "More" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "会员与用量" }));
    expect(requestNavigation).toHaveBeenCalledWith("/galaxy/membership");
  });
});
