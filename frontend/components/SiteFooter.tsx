import Link from "next/link";
import Image from "next/image";
import { UNNC_LOGO } from "@/lib/unnc-brand";
import { MATCH_ENTRY } from "@/lib/routes";

export default function SiteFooter() {
  return (
    <footer className="border-t border-unnc-blue/10 bg-gradient-to-b from-white to-unnc-sky/40 py-10 md:py-14">
      <div className="container max-w-7xl mx-auto px-4 md:px-8">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <Image
                src={UNNC_LOGO}
                alt=""
                width={48}
                height={48}
                className="h-10 w-auto max-h-10 object-contain opacity-90"
              />
              <div>
                <div className="text-xl font-bold bg-gradient-to-r from-unnc-navy to-unnc-blue bg-clip-text text-transparent">
                  NottFind
                </div>
                <p className="text-[10px] text-slate-500 mt-0.5">学生项目 · 非校方官网</p>
              </div>
            </div>
            <p className="text-sm text-gray-500 leading-relaxed">
              面向宁波诺丁汉大学同学：AI 实习匹配、校园活动与学习资讯聚合。视觉风格致敬 UNNC 官网。
            </p>
          </div>

          {/* Platform */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">平台</h3>
            <ul className="space-y-2.5 text-sm">
              <li>
                <Link href={MATCH_ENTRY} className="text-gray-500 hover:text-unnc-blue transition-colors">
                  实习匹配
                </Link>
              </li>
              <li>
                <Link href="/campus" className="text-gray-500 hover:text-unnc-blue transition-colors">
                  校园活动
                </Link>
              </li>
              <li>
                <Link href="/saved" className="text-gray-500 hover:text-unnc-blue transition-colors">
                  我的收藏
                </Link>
              </li>
            </ul>
          </div>

          {/* Data Sources */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900 mb-4">数据来源</h3>
            <ul className="space-y-2.5 text-sm">
              <li>
                <a href="https://www.shixiseng.com" target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-unnc-blue transition-colors">
                  实习僧
                </a>
              </li>
              <li>
                <a href="https://www.nowcoder.com" target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-unnc-blue transition-colors">
                  牛客网
                </a>
              </li>
              <li>
                <a href="https://www.nottingham.edu.cn" target="_blank" rel="noopener noreferrer" className="text-gray-500 hover:text-unnc-blue transition-colors font-medium">
                  宁波诺丁汉大学官网
                </a>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-gray-100 text-center text-sm text-gray-400 space-y-2">
          <p>© {new Date().getFullYear()} NottFind · 宁波诺丁汉大学学生团队</p>
          <p className="text-[11px] text-gray-400/90 leading-relaxed max-w-xl mx-auto">
            背景图致谢{" "}
            <a
              href="https://www.nottingham.edu.cn"
              target="_blank"
              rel="noopener noreferrer"
              className="text-gray-500 underline decoration-gray-300 underline-offset-2 hover:text-unnc-blue"
            >
              宁波诺丁汉大学官网
            </a>
            ；本站非校方运营。
          </p>
        </div>
      </div>
    </footer>
  );
}
