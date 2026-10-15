import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("real model evidence can be edited, approved and frozen without changing outcome", async ({
  page,
  request,
}) => {
  await page.goto("/?view=catalog&episode=0");
  const panel = page.getByRole("region", {
    name: "Episode analysis",
    exact: true,
  });
  await expect(
    panel.getByRole("heading", { name: "Model-assisted review" }).first(),
  ).toBeVisible();
  const suggestion = panel
    .locator("article.suggestion")
    .filter({ has: page.getByText("Pending review", { exact: true }) })
    .first();
  await expect(suggestion).toBeVisible();
  await suggestion
    .getByRole("combobox", { name: "Suggestion decision", exact: true })
    .selectOption("edit");
  await suggestion
    .getByLabel("Approved label")
    .fill("Browser fixture: reviewed interval");
  await suggestion.getByLabel("Approved start (s)").fill("0");
  await suggestion.getByLabel("Approved end (s)").fill("0.5");
  await suggestion
    .getByLabel("Suggestion review reason")
    .fill(
      "Automated workflow test in isolated catalog; not human semantic ground truth.",
    );
  await suggestion
    .getByRole("button", { name: "Save suggestion decision" })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Suggestion decision saved",
  );
  await expect(
    panel.getByText("Reviewed: edit", { exact: true }),
  ).toBeVisible();
  await expect(
    panel.getByText(/Approved annotation: Browser fixture: reviewed interval/),
  ).toContainText("0.00 to 0.50 s");
  const ep = await (await request.get("/api/episodes/0")).json();
  expect(
    ep.annotations.some(
      (a: any) => a.label === "Browser fixture: reviewed interval",
    ),
  ).toBeTruthy();
  expect(ep.reviews.every((r: any) => r.outcome === "unknown")).toBeTruthy();
  const created = await request.post("/api/versions", {
    data: {
      name: "Analysis provenance browser check",
      criteria: { valid_only: true },
    },
  });
  expect(created.ok()).toBeTruthy();
  const { id } = await created.json();
  const frozen = await (await request.get("/api/versions/" + id)).text();
  expect(
    JSON.parse(frozen).analysis_provenance.some(
      (p: any) => p.decision === "edit",
    ),
  ).toBeTruthy();
  const filter = await (
    await request.get(
      "/api/episodes?annotation_label=" +
        encodeURIComponent("Browser fixture: reviewed interval"),
    )
  ).json();
  expect(filter.items.map((e: any) => e.id)).toEqual([0]);
  const pending = panel
    .locator("article.suggestion")
    .filter({ has: page.getByText("Pending review", { exact: true }) })
    .first();
  if (await pending.count()) {
    await pending
      .getByRole("combobox", { name: "Suggestion decision", exact: true })
      .selectOption("reject");
    await pending
      .getByLabel("Suggestion review reason")
      .fill("Automated rejection path; isolated test catalog.");
    await pending
      .getByRole("button", { name: "Save suggestion decision" })
      .click();
    await expect(
      panel.getByText("Reviewed: reject", { exact: true }).first(),
    ).toBeVisible();
  }
  expect(await (await request.get("/api/versions/" + id)).text()).toBe(frozen);
  await panel
    .getByText("Sampled model evidence", { exact: true })
    .first()
    .click();
  await expect(panel.locator(".contact-sheet").first()).toBeVisible();
  await panel
    .getByText(/Diagnostic samples/)
    .first()
    .click();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await panel.screenshot({
    path: `${process.env.EPISODE_STORAGE}/evidence/analysis-desktop.png`,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await expect(
    panel.getByRole("button", { name: "Suggest annotations locally" }),
  ).toBeVisible();
  await panel
    .getByRole("button", { name: "Suggest annotations locally" })
    .focus();
  expect(
    (
      await new AxeBuilder({ page })
        .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await panel.screenshot({
    path: `${process.env.EPISODE_STORAGE}/evidence/analysis-narrow.png`,
  });
});
