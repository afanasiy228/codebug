#!/usr/bin/env node

const fs = require("fs/promises");
const path = require("path");

const DATABASE_URL =
    process.env.FIREBASE_DATABASE_URL ||
    process.env.PUBLIC_FIREBASE_WEB_DATABASE_URL ||
    "https://codebug-47347-default-rtdb.europe-west1.firebasedatabase.app";

const CLOUDINARY_CLOUD_NAME = process.env.CLOUDINARY_CLOUD_NAME || process.env.PUBLIC_CLOUDINARY_CLOUD_NAME || "";
const CLOUDINARY_UPLOAD_PRESET = process.env.CLOUDINARY_UPLOAD_PRESET || process.env.PUBLIC_CLOUDINARY_UPLOAD_PRESET || "";
const SHOULD_APPLY = process.argv.includes("--apply");
const CONFIRMED = process.argv.includes("--confirm-delete-base64");

function bytesOf(value) {
    return Buffer.byteLength(JSON.stringify(value ?? null), "utf8");
}

function isBase64Image(value) {
    return typeof value === "string" && /^data:image\/[a-z0-9.+-]+;base64,/i.test(value);
}

function safeSegment(value) {
    return encodeURIComponent(value);
}

async function readJson(pathName) {
    const response = await fetch(`${DATABASE_URL}/${pathName}.json`);
    const text = await response.text();
    if (!response.ok) {
        throw new Error(`Failed to read ${pathName}: HTTP ${response.status} ${text.slice(0, 200)}`);
    }
    return text === "null" ? null : JSON.parse(text);
}

async function patchJson(pathName, value) {
    const response = await fetch(`${DATABASE_URL}/${pathName}.json`, {
        method: "PATCH",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(value),
    });
    const text = await response.text();
    if (!response.ok) {
        throw new Error(`Failed to patch ${pathName}: HTTP ${response.status} ${text.slice(0, 200)}`);
    }
}

async function uploadDataUri(dataUri, folder, publicId) {
    if (!CLOUDINARY_CLOUD_NAME || !CLOUDINARY_UPLOAD_PRESET) {
        throw new Error("Cloudinary is not configured. Set CLOUDINARY_CLOUD_NAME and CLOUDINARY_UPLOAD_PRESET.");
    }

    const formData = new FormData();
    formData.append("file", dataUri);
    formData.append("upload_preset", CLOUDINARY_UPLOAD_PRESET);
    formData.append("folder", folder);
    formData.append("public_id", publicId);

    const response = await fetch(`https://api.cloudinary.com/v1_1/${CLOUDINARY_CLOUD_NAME}/image/upload`, {
        method: "POST",
        body: formData,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.secure_url) {
        throw new Error(data.error?.message || "Cloudinary upload failed");
    }
    return data.secure_url;
}

function collectImageTasks(users) {
    const tasks = [];
    for (const [login, user] of Object.entries(users || {})) {
        if (isBase64Image(user?.avatar)) {
            tasks.push({
                login,
                type: "avatar",
                sourcePath: `users/${login}/avatar`,
                targetUrlField: "avatarUrl",
                bytes: bytesOf(user.avatar),
                dataUri: user.avatar,
            });
        }

        const cover = user?.profileStyle?.customCover;
        if (isBase64Image(cover)) {
            tasks.push({
                login,
                type: "cover",
                sourcePath: `users/${login}/profileStyle/customCover`,
                targetUrlField: "coverUrl",
                bytes: bytesOf(cover),
                dataUri: cover,
            });
        }
    }
    return tasks;
}

async function writeBackup(users) {
    const backupsDir = path.join(__dirname, "..", "backups");
    const stamp = new Date().toISOString().replace(/[:.]/g, "-");
    const backupPath = path.join(backupsDir, `users-before-base64-migration-${stamp}.json`);
    await fs.mkdir(backupsDir, { recursive: true });
    await fs.writeFile(backupPath, JSON.stringify(users, null, 2));
    return backupPath;
}

async function applyTask(task) {
    const updatedAt = Date.now();
    const imageUrl = await uploadDataUri(task.dataUri, `codebug/${task.login}`, task.type);

    if (task.type === "avatar") {
        await patchJson(`users/${safeSegment(task.login)}`, {
            avatarUrl: imageUrl,
            avatar: null,
            updatedAt,
        });
        await patchJson(`publicProfiles/${safeSegment(task.login)}`, {
            avatarUrl: imageUrl,
            updatedAt,
        });
        await patchJson(`ratingLeaderboard/${safeSegment(task.login)}`, {
            avatarUrl: imageUrl,
            updatedAt,
        });
    }

    if (task.type === "cover") {
        await patchJson(`users/${safeSegment(task.login)}`, {
            coverUrl: imageUrl,
            "profileStyle/customCover": null,
            updatedAt,
        });
        await patchJson(`publicProfiles/${safeSegment(task.login)}`, {
            coverUrl: imageUrl,
            updatedAt,
        });
        await patchJson(`ratingLeaderboard/${safeSegment(task.login)}/profileStyle`, {
            coverUrl: imageUrl,
        });
    }

    return imageUrl;
}

async function main() {
    const users = await readJson("users");
    const tasks = collectImageTasks(users || {});
    const avatarTasks = tasks.filter((task) => task.type === "avatar");
    const coverTasks = tasks.filter((task) => task.type === "cover");

    console.log(JSON.stringify({
        mode: SHOULD_APPLY ? "apply" : "dry-run",
        usersBytes: bytesOf(users),
        avatarBase64Users: avatarTasks.length,
        coverBase64Users: coverTasks.length,
        totalBase64Bytes: tasks.reduce((sum, task) => sum + task.bytes, 0),
        plannedChanges: tasks.map(({ login, type, sourcePath, targetUrlField, bytes }) => ({
            login,
            type,
            sourcePath,
            targetUrlField,
            bytes,
        })),
    }, null, 2));

    if (!SHOULD_APPLY) {
        console.log("\nDry-run only. To migrate images, run with: --apply --confirm-delete-base64");
        return;
    }
    if (!CONFIRMED) throw new Error("Refusing to apply without --confirm-delete-base64");

    const backupPath = await writeBackup(users);
    console.log(`Backup written: ${backupPath}`);

    for (const task of tasks) {
        try {
            const imageUrl = await applyTask(task);
            console.log(`Migrated ${task.sourcePath} -> ${imageUrl}`);
        } catch (error) {
            console.error(`Skipped ${task.sourcePath}: ${error.message || error}`);
        }
    }
}

main().catch((error) => {
    console.error(error.message || error);
    process.exit(1);
});
