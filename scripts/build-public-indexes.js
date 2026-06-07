#!/usr/bin/env node

const DATABASE_URL =
    process.env.FIREBASE_DATABASE_URL ||
    process.env.PUBLIC_FIREBASE_WEB_DATABASE_URL ||
    "https://codebug-47347-default-rtdb.europe-west1.firebasedatabase.app";

const SHOULD_APPLY = process.argv.includes("--apply");
const CONFIRMED = process.argv.includes("--confirm");

function bytesOf(value) {
    return Buffer.byteLength(JSON.stringify(value ?? null), "utf8");
}

function isBase64Image(value) {
    return typeof value === "string" && /^data:image\/[a-z0-9.+-]+;base64,/i.test(value);
}

function lightStats(user) {
    const stats = user?.stats && typeof user.stats === "object" ? user.stats : {};
    const solvedValue = stats.cnt ?? stats.solved ?? user?.solved ?? 0;
    const solved = typeof solvedValue === "object" && solvedValue
        ? Object.keys(solvedValue).length
        : Number(solvedValue || 0) || 0;

    return {
        exp: Number(stats.exp ?? user?.exp ?? 0) || 0,
        cnt: solved,
        rating: Number(stats.rating ?? 0) || 0,
    };
}

function lightProfileStyle(user) {
    const style = user?.profileStyle && typeof user.profileStyle === "object" ? user.profileStyle : {};
    return {
        coverId: style.coverId || null,
        coverUrl: typeof user?.coverUrl === "string" ? user.coverUrl : "",
    };
}

function lightSubscription(user) {
    const sub = user?.subscription && typeof user.subscription === "object" ? user.subscription : null;
    if (!sub) return null;
    return {
        tier: sub.tier || "",
        status: sub.status || "",
        expiresAt: sub.expiresAt || null,
        graceUntil: sub.graceUntil || sub.paymentGraceUntil || null,
        visuals: sub.visuals || null,
        features: sub.features || null,
        updatedAt: sub.updatedAt || null,
    };
}

function buildIndexes(users) {
    const publicProfiles = {};
    const ratingLeaderboard = {};

    for (const [login, user] of Object.entries(users || {})) {
        const stats = lightStats(user);
        const avatarUrl = typeof user?.avatarUrl === "string" ? user.avatarUrl : "";
        const coverUrl = typeof user?.coverUrl === "string" ? user.coverUrl : "";
        const profileStyle = lightProfileStyle(user);
        const subscription = lightSubscription(user);
        const updatedAt = user?.updatedAt || Date.now();

        publicProfiles[login] = {
            login: user?.login || login,
            avatarUrl,
            coverUrl,
            stats,
            profileStyle: { coverId: profileStyle.coverId },
            subscription,
            updatedAt,
        };

        ratingLeaderboard[login] = {
            login: user?.login || login,
            exp: stats.exp,
            cnt: stats.cnt,
            rating: stats.rating,
            avatarUrl,
            profileStyle,
            subscription,
            updatedAt,
        };
    }

    return { publicProfiles, ratingLeaderboard };
}

async function readJson(path) {
    const response = await fetch(`${DATABASE_URL}/${path}.json`);
    const text = await response.text();
    if (!response.ok) {
        throw new Error(`Failed to read ${path}: HTTP ${response.status} ${text.slice(0, 200)}`);
    }
    return text === "null" ? null : JSON.parse(text);
}

async function writeJson(path, value) {
    const response = await fetch(`${DATABASE_URL}/${path}.json`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(value),
    });
    const text = await response.text();
    if (!response.ok) {
        throw new Error(`Failed to write ${path}: HTTP ${response.status} ${text.slice(0, 200)}`);
    }
}

async function main() {
    const users = await readJson("users");
    const { publicProfiles, ratingLeaderboard } = buildIndexes(users || {});
    const base64Summary = Object.entries(users || {}).reduce(
        (acc, [login, user]) => {
            if (isBase64Image(user?.avatar)) {
                acc.avatarCount += 1;
                acc.avatarBytes += bytesOf(user.avatar);
                acc.affectedUsers.add(login);
            }
            const cover = user?.profileStyle?.customCover;
            if (isBase64Image(cover)) {
                acc.coverCount += 1;
                acc.coverBytes += bytesOf(cover);
                acc.affectedUsers.add(login);
            }
            return acc;
        },
        { avatarCount: 0, avatarBytes: 0, coverCount: 0, coverBytes: 0, affectedUsers: new Set() }
    );

    console.log(JSON.stringify({
        mode: SHOULD_APPLY ? "apply" : "dry-run",
        usersCount: Object.keys(users || {}).length,
        usersBytes: bytesOf(users),
        ratingLeaderboardBytes: bytesOf(ratingLeaderboard),
        publicProfilesBytes: bytesOf(publicProfiles),
        base64NotCopied: {
            avatarCount: base64Summary.avatarCount,
            avatarBytes: base64Summary.avatarBytes,
            coverCount: base64Summary.coverCount,
            coverBytes: base64Summary.coverBytes,
            affectedUsers: Array.from(base64Summary.affectedUsers).sort(),
        },
    }, null, 2));

    if (!SHOULD_APPLY) {
        console.log("\nDry-run only. To write indexes, run with: --apply --confirm");
        return;
    }
    if (!CONFIRMED) throw new Error("Refusing to write indexes without --confirm");

    await writeJson("publicProfiles", publicProfiles);
    await writeJson("ratingLeaderboard", ratingLeaderboard);
    console.log("Indexes written: publicProfiles, ratingLeaderboard");
}

main().catch((error) => {
    console.error(error.message || error);
    process.exit(1);
});
