/** 宁波诺丁汉大学官网公开静态资源（仅作视觉致敬，版权归原作者所有） */
export const UNNC_ORIGIN = "https://www.nottingham.edu.cn";

export const UNNC_LOGO = `${UNNC_ORIGIN}/SiteElements/Images/2023-Revamp/Logo/UoN-Logo.jpg`;

/** 首页 Hero 轮播：均为官网公开横幅图（桌面 1920×1080 类资源） */
export const UNNC_HERO_IMAGES = [
  `${UNNC_ORIGIN}/SiteElements/Images/2023-Revamp/Images/Homepage/Home-Traits-Cover-Desktop-1920x1080.jpeg`,
  `${UNNC_ORIGIN}/image-library/Homepage-banner/sitting-on-trent-lawn-19201080.x350206fe.jpg`,
  `${UNNC_ORIGIN}/image-library/Homepage-banner/Study-with-us/2023-revamp/Study-Banner-4-Desktop-1920x1080.x386cbeb9.jpg`,
  `${UNNC_ORIGIN}/image-library/Homepage-banner/2025-QS-top-100/QS100-1920x1080.xb485df2f.jpg`,
  `${UNNC_ORIGIN}/image-library/Homepage-banner/20251218-three-new-UG-programme/homepage-three-new-UG-programme-1920x1080.x4c9bb327.jpg`,
] as const;

/** @deprecated 请使用 UNNC_HERO_IMAGES；保留首图兼容旧引用 */
export const UNNC_HERO_IMAGE = UNNC_HERO_IMAGES[0];
