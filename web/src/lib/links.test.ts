import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { MAX_LINKS_PER_REQUEST, extractReelLinks, parseReelUrl, toRpcItems } from "./links.ts";

describe("parseReelUrl", () => {
  it("reconnaît un reel Instagram partagé depuis l'app, sans le paramètre de suivi", () => {
    assert.deepEqual(parseReelUrl("https://www.instagram.com/reel/C1abcDEF_-9/?igsh=MWQ1ZGUxMzBkMA=="), {
      platform: "instagram",
      externalId: "C1abcDEF_-9",
      sourceUrl: "https://www.instagram.com/reel/C1abcDEF_-9/",
    });
  });

  it("accepte les variantes /reels/, /p/, /tv/, avec nom d'utilisateur et sans www", () => {
    for (const url of [
      "https://instagram.com/reels/C1abcDEF",
      "https://www.instagram.com/p/C1abcDEF/",
      "https://m.instagram.com/tv/C1abcDEF/",
      "https://www.instagram.com/chef.paul/reel/C1abcDEF/",
    ]) {
      assert.equal(parseReelUrl(url)?.externalId, "C1abcDEF", url);
    }
  });

  it("reconnaît YouTube Shorts, youtu.be et watch", () => {
    for (const url of [
      "https://youtube.com/shorts/dQw4w9WgXcQ?si=abc",
      "https://youtu.be/dQw4w9WgXcQ",
      "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10",
    ]) {
      const link = parseReelUrl(url);
      assert.equal(link?.platform, "youtube", url);
      assert.equal(link?.sourceUrl, "https://www.youtube.com/shorts/dQw4w9WgXcQ");
    }
  });

  it("ignore les profils, les autres sites et les URLs piégées", () => {
    for (const url of [
      "https://www.instagram.com/chef.paul/",
      "https://www.instagram.com/stories/chef/123/",
      "https://instagram.com.evil.example/reel/C1abcDEF/",
      "https://evil.example/?u=https://instagram.com/reel/C1abcDEF",
      "javascript:alert(1)",
      "https://www.youtube.com/watch?v=short",
      "not a url",
    ]) {
      assert.equal(parseReelUrl(url), null, url);
    }
  });
});

describe("extractReelLinks", () => {
  it("extrait les liens d'un texte de partage et retire la ponctuation finale", () => {
    const text =
      "Regarde ça !! https://www.instagram.com/reel/C1abcDEF/?igsh=xyz). Et ça : https://youtu.be/dQw4w9WgXcQ.";
    const links = extractReelLinks(text);
    assert.deepEqual(
      links.map((l) => l.externalId),
      ["C1abcDEF", "dQw4w9WgXcQ"],
    );
  });

  it("déduplique", () => {
    const text = "https://instagram.com/reel/C1abcDEF https://www.instagram.com/reel/C1abcDEF/?igsh=1";
    assert.equal(extractReelLinks(text).length, 1);
  });

  it("plafonne le nombre de liens par requête", () => {
    const text = Array.from(
      { length: 40 },
      (_, i) => `https://instagram.com/reel/Cxyz${String(i).padStart(4, "0")}`,
    ).join("\n");
    assert.equal(extractReelLinks(text).length, MAX_LINKS_PER_REQUEST);
  });

  it("produit le format attendu par la base", () => {
    const [item] = toRpcItems(extractReelLinks("https://instagram.com/reel/C1abcDEF"));
    assert.deepEqual(item, {
      platform: "instagram",
      external_id: "C1abcDEF",
      source_url: "https://www.instagram.com/reel/C1abcDEF/",
    });
  });
});
