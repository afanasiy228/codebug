import fs from "node:fs";
import test, { after, before } from "node:test";
import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
} from "@firebase/rules-unit-testing";

let env;

before(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-codebug",
    database: {
      rules: fs.readFileSync("firebase.database.rules.json", "utf8"),
    },
  });
  await env.withSecurityRulesDisabled(async (context) => {
    await context.database().ref("/").set({
      users: {
        alice: {
          id: "uid-alice",
          email: "alice@example.test",
          stats: { exp: 10, cnt: 1, rating: 2, solved: { 1: true } },
          subscription: { tier: "pro", status: "active", source: "payment" },
          friends: { bob: { addedAt: Date.now() } },
        },
        bob: {
          id: "uid-bob",
          email: "bob@example.test",
          stats: { exp: 0, cnt: 0, rating: 0 },
          presence: { online: true, lastSeen: Date.now() },
        },
        rootadmin: { id: "uid-admin", email: "admin@example.test" },
      },
      publicProfiles: {
        alice: { login: "alice", stats: { exp: 10, cnt: 1, rating: 2 } },
      },
      ratingLeaderboard: {
        alice: { login: "alice", exp: 10, cnt: 1, rating: 2 },
      },
      userAuthMap: {
        "uid-alice": "alice",
        "uid-bob": "bob",
        "uid-admin": "rootadmin",
      },
      emailToLogin: {
        "alice@example,test": "alice",
        "bob@example,test": "bob",
      },
      admins: { rootadmin: true },
      submissions: { global: { one: { login: "alice", task: 1, verdict: "OK" } } },
      contests: { public: { title: "Contest" } },
      contest_regs: { public: { alice: { login: "alice" } } },
    });
  });
});

after(async () => {
  await env?.cleanup();
});

const dbFor = (uid) => env.authenticatedContext(uid).database();

test("anonymous users only read explicitly public projections", async () => {
  const db = env.unauthenticatedContext().database();
  await assertSucceeds(db.ref("publicProfiles").once("value"));
  await assertSucceeds(db.ref("ratingLeaderboard").once("value"));
  await assertSucceeds(db.ref("submissions/global").once("value"));
  await assertFails(db.ref("users/alice").once("value"));
  await assertFails(db.ref("users/alice/email").once("value"));
  await assertFails(db.ref("userAuthMap").once("value"));
  await assertFails(db.ref("emailToLogin").once("value"));
  await assertFails(db.ref("users").remove());
});

test("a user reads private data only for their own account", async () => {
  const alice = dbFor("uid-alice");
  await assertSucceeds(alice.ref("users/alice").once("value"));
  await assertSucceeds(alice.ref("userAuthMap/uid-alice").once("value"));
  await assertSucceeds(alice.ref("users/bob/presence").once("value"));
  await assertFails(alice.ref("users/bob").once("value"));
  await assertFails(alice.ref("users/bob/email").once("value"));
  await assertFails(alice.ref("userAuthMap/uid-bob").once("value"));
  await assertFails(alice.ref("emailToLogin/alice@example,test").once("value"));
});

test("a user cannot grant stats, rating, subscription or identity", async () => {
  const alice = dbFor("uid-alice");
  await assertFails(alice.ref("users/alice/stats/exp").set(999999));
  await assertFails(alice.ref("users/alice/subscription/tier").set("pro_plus"));
  await assertFails(alice.ref("users/alice/id").set("uid-attacker"));
  await assertFails(alice.ref("publicProfiles/alice/stats/exp").set(999999));
  await assertFails(alice.ref("ratingLeaderboard/alice/rating").set(999999));
  await assertFails(alice.ref("admins/alice").set(true));
  await assertFails(alice.ref("submissions/global/fake").set({ verdict: "OK" }));
});

test("a user can update only safe profile and social fields", async () => {
  const alice = dbFor("uid-alice");
  await assertSucceeds(alice.ref("users/alice/presence").update({
    online: true,
    lastSeen: Date.now(),
  }));
  await assertSucceeds(alice.ref("users/alice/friends/bob").set({
    addedAt: Date.now(),
  }));
  await assertSucceeds(alice.ref("users/alice/avatarUrl").set("https://res.cloudinary.com/example/avatar.png"));
  await assertSucceeds(alice.ref("publicProfiles/alice/avatarUrl").set("https://res.cloudinary.com/example/avatar.png"));
  await assertSucceeds(alice.ref("ratingLeaderboard/alice/avatarUrl").set("https://res.cloudinary.com/example/avatar.png"));
  await assertFails(alice.ref("users/bob/avatarUrl").set("https://evil.example/avatar.png"));
});

test("task suggestions are create-only and bound to the authenticated login", async () => {
  const alice = dbFor("uid-alice");
  const suggestion = {
    title: "Task",
    statement: "Statement",
    buggyCode: "int main() {}",
    bugExplanation: "A sufficiently long explanation",
    author: "alice",
    createdAt: Date.now(),
    status: "pending",
  };
  await assertSucceeds(alice.ref("taskSuggestions/new").set(suggestion));
  await assertFails(alice.ref("taskSuggestions/spoofed").set({ ...suggestion, author: "bob" }));
  await assertFails(alice.ref("taskSuggestions/new").update({ status: "approved" }));
});

test("an authenticated database admin retains operational access", async () => {
  const admin = dbFor("uid-admin");
  await assertSucceeds(admin.ref("/").once("value"));
  await assertSucceeds(admin.ref("tasksHidden/123").set(true));
  await assertSucceeds(admin.ref("users/alice/stats/exp").set(11));
});
