import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
test("complete real-data curation journey produces verified immutable version", async ({
  page,
  request,
}) => {
  test.setTimeout(120000);
  const stamp = Date.now();
  for (const id of [0, 1, 2]) {
    await page.goto("/?view=catalog&episode=" + id);
    await page
      .getByLabel("Review reason")
      .fill(
        "Automated demonstration review: video and signals inspected; task outcome remains unknown.",
      );
    await page
      .getByRole("button", { name: "Save review", exact: true })
      .click();
    await expect(page.getByRole("status")).toContainText("Review recorded");
  }
  await page.goto("/?view=catalog&episode=0");
  await page
    .getByLabel("Interval label", { exact: true })
    .fill("Demonstration: approach interval");
  await page
    .getByLabel("Notes", { exact: true })
    .fill("Automated browser journey annotation. No task-success claim.");
  await page
    .getByRole("button", { name: "Save annotation", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Interval annotation saved",
  );
  await page.getByRole("button", { name: "Selections", exact: true }).click();
  await page
    .getByLabel("Selection name")
    .fill("Accepted demonstration " + stamp);
  await page.getByLabel("Review filter").selectOption("accepted");
  await page.getByRole("button", { name: "Save criteria" }).click();
  await expect(page.getByRole("status")).toContainText("Selection saved");
  await page
    .getByRole("button", { name: "Dataset versions", exact: true })
    .click();
  await page
    .getByLabel("Version name")
    .fill("Browser verified subset " + stamp);
  await page
    .getByLabel("Selection", { exact: true })
    .selectOption({ label: "Accepted demonstration " + stamp });
  await page
    .getByRole("button", { name: "Create version", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Immutable version published",
  );
  await expect(page.getByText("3 episodes · seed 17")).toBeVisible();
  const versions = await (await request.get("/api/versions")).json();
  const id = versions[0].id;
  const frozen = await (await request.get("/api/versions/" + id)).text();
  await page
    .getByRole("button", { name: "Verify consumer", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText(
    "Consumer verification queued",
  );
  await expect
    .poll(
      async () => {
        const rows = await (await request.get("/api/verifications")).json();
        return rows.some(
          (v: any) =>
            v.version === id && JSON.parse(v.result).status === "passed",
        );
      },
      { timeout: 90000 },
    )
    .toBeTruthy();
  await request.post("/api/episodes/0/review", {
    data: {
      status: "accepted",
      reason:
        "Later automated review revision; prior version must remain unchanged.",
    },
  });
  expect(await (await request.get("/api/versions/" + id)).text()).toBe(frozen);
  await page.getByRole("button", { name: "Verification", exact: true }).click();
  await expect(page.getByText(/24 decoded images/).first()).toBeVisible();
  const result = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
    .analyze();
  expect(result.violations).toEqual([]);
  await page.screenshot({
    path: `${process.env.EPISODE_STORAGE || "/Volumes/External Storage/Episode"}/evidence/verification-desktop.png`,
    fullPage: true,
  });
});
test("catalog filters, explicit fault demonstration, version comparison and narrow navigation", async ({
  page,
  request,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/?view=catalog");
  await page.getByLabel("Review status").selectOption("accepted");
  await expect(page.getByText("3 matching episodes")).toBeVisible();
  await page
    .getByRole("button", { name: "Quality review", exact: true })
    .click();
  await page.getByRole("button", { name: "Run labelled fault checks" }).click();
  await expect(
    page.getByRole("heading", { name: "Injected: nonfinite action" }),
  ).toBeVisible();
  await expect(page.getByText("Detected: feature.finite")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  for (const view of ["selections", "versions", "jobs", "verification"]) {
    await page.goto("/?view=" + view);
    await expect(page.locator("h1")).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    const result = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(result.violations).toEqual([]);
  }
  const v = await (await request.get("/api/versions")).json();
  const comparison = await (
    await request.get(
      `/api/compare?left=${v[v.length - 1].id}&right=${v[0].id}`,
    )
  ).json();
  expect(comparison.removed.length).toBe(47);
});
