import { useAuth } from "./auth";

// Lämäri is in Finnish for Finnish readers and in English for everyone else.
// t("key", { name: "..." }) fills {name} placeholders.

const EN = {
  // page
  tabTeam: "Team", tabCoach: "Coach", tabMatches: "Matches", tabPrizes: "Prizes", tabCompete: "Compete",
  season: "Liiga {season}", gameweek: "Gameweek {n}", locksIn: "Locks in {left}", startsIn: "in {left}", live: "LIVE",
  topScorers: "{time}. Top fantasy scorers this season.", backToProfile: "Back to profile", close: "Close",
  // team
  statPoints: "Points", statFinland: "Finland", statLastGw: "Last GW", statBank: "Bank",
  prizesBy: "Gameweek prizes by", lineup: "Gameweek {n} lineup", tapCaptain: "Tap a starter to make him captain",
  nowCaptain: "{name} is captain for GW{n} and scores double.", pointsPerGw: "Points per gameweek",
  forwards: "Forwards", defence: "Defence", goalie: "Goalie", bench: "Bench", pts: "{n} pts",
  // coach
  review: "Gameweek {n} review", picks: "Picks for gameweek {n}", news: "News about your players",
  kaleva: "Kaleva", liigaStats: "Liiga stats", writingStory: "Our newsroom is writing this story for your feed.",
  source: "Source: Kaleva", original: "Original article", aiWording: "Worded by AI. Figures from Liiga.",
  // matches
  fan: "Fan", newToHockey: "New to hockey", short: "Short", full: "Full", sponsored: "Sponsored", ot: "OT", so: "SO",
  prevGw: "Previous gameweek", nextGw: "Next gameweek",
  // prizes
  inTeam: "In your team", notInTeam: "Not in your team", bestWeek: "Your best week: {n}", youAre: "You are {tier}",
  wonRank: "finished #{rank}", wonPlayer: "your pick scored", wonPoints: "{n}+ points", wonTier: "season tier",
  vouchers: "Your vouchers", won: "{n} won", voucherLine: "Gameweek {gw}, {how}. Valid until {date}.", showCode: "Show code",
  standing: "#{rank} of {managers} managers this season.", placesTo: "{n} places to {tier}.", placeTo: "1 place to {tier}.",
  gwPrizes: "Gameweek {n} prizes", starts: "Starts in {left}", seasonPrizes: "Season prizes",
  examples: "Example prizes for this prototype.", placeOne: "#{n}", placeRange: "#{a} to #{b}",
  diamond: "Diamond", gold: "Gold", silver: "Silver", bronze: "Bronze",
  // compete
  leaderboards: "Leaderboards", privateLeagues: "Private leagues", seasonTab: "Season", gwTab: "GW{n}", today: "Today",
  finland: "Finland", oulu: "Oulu", noPoints: "No points here yet.", jumpToMe: "Jump to my position (#{n})",
  newLeague: "New league name", create: "Create", inviteCode: "Invite code, e.g. 2GDKGY", join: "Join",
  managers: "{n} managers", youRank: ", you are #{n}", copyCode: "Copy invite code",
  inviteFriend: "Invite a friend by @username", invite: "Invite", joined: "@{user} joined {league}.",
  previous: "Previous", next: "Next",
  // chat
  coachTitle: "Your Lämäri coach", askCoach: "Ask your coach", send: "Send", loading: "Loading Lämäri",
  greeting: "Hi @{user}. I'm your Lämäri coach, here to help you top the leaderboard. What do you want to work on?",
  starters: ["How do I climb the leaderboard?", "Who should I captain?", "Who should I start or bench?",
    "Which transfer gains me points?", "Which prizes can I still win?"],
  // squad builder
  makeTeam: "Make your team", makeTeamHelp: "Pick 15 Liiga players: 2 goalies, 5 defenders and 8 forwards. Max 3 from one team.",
  budgetLeft: "budget left", players: "players", quickPick: "Quick pick", goalies: "Goalies", defenders: "Defence",
  forwardsTab: "Forwards", search: "Search player or team", full_: "{pos} full", threeFrom: "3 from {team} already",
  overBudget: "Over budget", injured: "injured", ptsShort: "pts", price: "price", showMore: "Show more ({n} left)",
  teamName: "Team name, e.g. Raksila Rockets", saving: "Saving…", createTeam: "Create team",
};

const FI = {
  tabTeam: "Joukkue", tabCoach: "Valmentaja", tabMatches: "Ottelut", tabPrizes: "Palkinnot", tabCompete: "Kilpailu",
  season: "Liiga {season}", gameweek: "Kierros {n}", locksIn: "Lukittuu {left} päästä", startsIn: "{left} päästä", live: "LIVE",
  topScorers: "{time}. Kauden eniten Lämäri-pisteitä tehneet.", backToProfile: "Takaisin profiiliin", close: "Sulje",
  statPoints: "Pisteet", statFinland: "Suomi", statLastGw: "Edell. kierros", statBank: "Pankki",
  prizesBy: "Kierroksen palkinnot:", lineup: "Kierroksen {n} kokoonpano", tapCaptain: "Napauta aloittajaa, niin hänestä tulee kapteeni",
  nowCaptain: "{name} on kapteeni kierroksella {n} ja tekee tuplapisteet.", pointsPerGw: "Pisteet kierroksittain",
  forwards: "Hyökkääjät", defence: "Puolustajat", goalie: "Maalivahti", bench: "Penkki", pts: "{n} p",
  review: "Kierroksen {n} katsaus", picks: "Valinnat kierrokselle {n}", news: "Uutisia pelaajistasi",
  kaleva: "Kaleva", liigaStats: "Liigan tilastot", writingStory: "Toimituksemme kirjoittaa tästä jutun syötteeseesi.",
  source: "Lähde: Kaleva", original: "Alkuperäinen juttu", aiWording: "Tekoälyn muotoilema. Luvut Liigasta.",
  fan: "Fani", newToHockey: "Uusi lajissa", short: "Lyhyt", full: "Laaja", sponsored: "Mainos", ot: "JA", so: "VL",
  prevGw: "Edellinen kierros", nextGw: "Seuraava kierros",
  inTeam: "Joukkueessasi", notInTeam: "Ei joukkueessasi", bestWeek: "Paras kierroksesi: {n}", youAre: "Tasosi: {tier}",
  wonRank: "sijoitus {rank}.", wonPlayer: "valintasi teki pisteitä", wonPoints: "{n}+ pistettä", wonTier: "kauden taso",
  vouchers: "Lahjakorttisi", won: "{n} voitettu", voucherLine: "Kierros {gw}, {how}. Voimassa {date} asti.", showCode: "Näytä koodi",
  standing: "Sija {rank}/{managers} tällä kaudella.", placesTo: "{n} sijaa tasolle {tier}.", placeTo: "1 sija tasolle {tier}.",
  gwPrizes: "Kierroksen {n} palkinnot", starts: "Alkaa {left} päästä", seasonPrizes: "Kauden palkinnot",
  examples: "Palkinnot ovat esimerkkejä tässä prototyypissä.", placeOne: "{n}.", placeRange: "sijat {a}-{b}",
  diamond: "Timantti", gold: "Kulta", silver: "Hopea", bronze: "Pronssi",
  leaderboards: "Tulostaulut", privateLeagues: "Omat liigat", seasonTab: "Kausi", gwTab: "Kierros {n}", today: "Tänään",
  finland: "Suomi", oulu: "Oulu", noPoints: "Ei vielä pisteitä.", jumpToMe: "Siirry omaan sijaasi ({n}.)",
  newLeague: "Uuden liigan nimi", create: "Luo", inviteCode: "Kutsukoodi, esim. 2GDKGY", join: "Liity",
  managers: "{n} pelaajaa", youRank: ", olet {n}.", copyCode: "Kopioi kutsukoodi",
  inviteFriend: "Kutsu kaveri @käyttäjänimellä", invite: "Kutsu", joined: "@{user} liittyi liigaan {league}.",
  previous: "Edellinen", next: "Seuraava",
  coachTitle: "Lämäri-valmentajasi", askCoach: "Kysy valmentajalta", send: "Lähetä", loading: "Lämäri latautuu",
  greeting: "Moi @{user}. Olen Lämäri-valmentajasi ja autan sinua nousemaan tulostaulukon kärkeen. Mistä aloitetaan?",
  starters: ["Miten nousen tulostaulukossa?", "Kenet valitsen kapteeniksi?", "Kuka aloittaa, kuka penkille?",
    "Mikä vaihto tuo pisteitä?", "Mitä palkintoja voin vielä voittaa?"],
  makeTeam: "Kokoa joukkueesi", makeTeamHelp: "Valitse 15 Liigan pelaajaa: 2 maalivahtia, 5 puolustajaa ja 8 hyökkääjää. Enintään 3 samasta joukkueesta.",
  budgetLeft: "budjettia jäljellä", players: "pelaajaa", quickPick: "Pikavalinta", goalies: "Maalivahdit", defenders: "Puolustajat",
  forwardsTab: "Hyökkääjät", search: "Hae pelaajaa tai joukkuetta", full_: "{pos}: täynnä", threeFrom: "Jo 3 pelaajaa joukkueesta {team}",
  overBudget: "Budjetti ylittyy", injured: "loukkaantunut", ptsShort: "p", price: "hinta", showMore: "Näytä lisää ({n} jäljellä)",
  teamName: "Joukkueen nimi, esim. Raksilan Raketit", saving: "Tallennetaan…", createTeam: "Luo joukkue",
};

export function useT() {
  const { me } = useAuth();
  const lang = me?.preferred_language === "fi" ? "fi" : "en";
  const dict = lang === "fi" ? FI : EN;
  const t = (key, vars = {}) => {
    const value = dict[key] ?? EN[key] ?? key;
    return typeof value === "string" ? value.replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? "")) : value;
  };
  t.lang = lang;
  t.locale = lang === "fi" ? "fi-FI" : "en-GB";
  return t;
}
