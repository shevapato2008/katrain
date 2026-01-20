/**
 * KaTrain Rank Mapping Utility
 * Internal scale:
 * -19 to 0  => 20k to 1k (Kyu ranks)
 * 1 to 9    => 1d to 9d (Dan ranks)
 */

export const internalToRank = (val: number | string | null | undefined): string => {
    if (val === null || val === undefined || val === "") return "No Rank";
    
    // Handle string inputs if they come as "-19" etc.
    const num = typeof val === "string" ? parseInt(val, 10) : val;
    if (isNaN(num)) return val.toString(); // Fallback if it's already a rank string like "20k"

    if (num <= 0) {
        // 0 -> 1k, -1 -> 2k, -19 -> 20k
        const kyu = 1 - num;
        return `${kyu}k`;
    } else {
        // 1 -> 1d, 9 -> 9d
        return `${num}d`;
    }
};

/**
 * Maps the 0-28 slider value to KaTrain's internal rank number.
 * Slider 0 (20k) -> -19
 * Slider 19 (1k) -> 0
 * Slider 20 (1d) -> 1
 * Slider 28 (9d) -> 9
 */
export const sliderToInternal = (sliderVal: number): number => {
    if (sliderVal <= 19) {
        return sliderVal - 19; // 0 -> -19, 19 -> 0
    } else {
        return sliderVal - 19; // 20 -> 1, 28 -> 9
    }
};

/**
 * Maps the 0-28 slider value to human_kyu_rank expected by KaTrain engine.
 * engine expects: 20...1 for kyu, 0...-8 for dan.
 */
export const sliderToHumanKyuRank = (sliderVal: number): number => {
    if (sliderVal <= 19) {
        return 20 - sliderVal; // 0 -> 20, 19 -> 1
    } else {
        return 19 - sliderVal; // 20 -> -1, 28 -> -9 -> but max is -8
    }
};

/**
 * Maps the 0-28 slider value to human_kyu_rank expected by KaTrain engine.
 * engine expects: 20...1 for kyu, 0...-8 for dan.
 */
export const sliderToHumanKyuRankFixed = (sliderVal: number): number => {
    if (sliderVal <= 19) {
        return 20 - sliderVal; // 0 -> 20, 19 -> 1
    } else {
        // 20 -> 0 (1d), 21 -> -1 (2d), ..., 28 -> -8 (9d)
        return 20 - sliderVal;
    }
};

export const rankToSlider = (rank: string): number => {
    const r = rank.toLowerCase();
    if (r.includes('k')) {
        const k = parseInt(r.replace('k', ''), 10);
        return Math.max(0, 20 - k);
    }
    if (r.includes('d')) {
        const d = parseInt(r.replace('d', ''), 10);
        return Math.min(28, 19 + d);
    }
    return 0;
};
