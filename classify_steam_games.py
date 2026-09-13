# -*- coding: utf-8 -*-
"""根据 steam_library.json 对每款游戏进行五维分类，输出指定 JSON 格式。"""
import json
import re

INPUT_FILE = 'steam_library.json'
OUTPUT_FILE = 'steam_library_classified.json'

# 已知游戏的精准分类（名称小写匹配或包含）
KNOWN = {
    "left 4 dead": {"primary": "射击 (FPS/TPS)", "sub": "合作生存射击", "vibe": "紧张爽快", "intensity": "高", "slogan": "四人一狗，僵尸不够杀。"},
    "left 4 dead 2": {"primary": "射击 (FPS/TPS)", "sub": "合作生存射击", "vibe": "紧张爽快", "intensity": "高", "slogan": "打僵尸的尽头是打队友。"},
    "plants vs. zombies": {"primary": "策略/模拟", "sub": "塔防", "vibe": "解压/治愈", "intensity": "低", "slogan": "种向日葵比种田还上瘾。"},
    "shank": {"primary": "动作/冒险", "sub": "横版清版", "vibe": "硬核暴力", "intensity": "中", "slogan": "小刀拉屁股，开开眼。"},
    "hitman": {"primary": "动作/冒险", "sub": "潜行暗杀", "vibe": "冷静算计", "intensity": "中", "slogan": "西装暴徒，优雅灭口。"},
    "bioshock": {"primary": "射击 (FPS/TPS)", "sub": "叙事FPS", "vibe": "黑暗/反乌托邦", "intensity": "高", "slogan": "海底乌托邦，哲学与霰弹枪。"},
    "bioshock 2": {"primary": "射击 (FPS/TPS)", "sub": "叙事FPS", "vibe": "黑暗/反乌托邦", "intensity": "高", "slogan": "当爹的代价是扛钻头。"},
    "bioshock infinite": {"primary": "射击 (FPS/TPS)", "sub": "叙事FPS", "vibe": "蒸汽朋克/多重宇宙", "intensity": "高", "slogan": "天空城、少女与无限轮回。"},
    "bioshock remastered": {"primary": "射击 (FPS/TPS)", "sub": "叙事FPS", "vibe": "黑暗/反乌托邦", "intensity": "高", "slogan": "海底乌托邦高清重制版。"},
    "bioshock 2 remastered": {"primary": "射击 (FPS/TPS)", "sub": "叙事FPS", "vibe": "黑暗/反乌托邦", "intensity": "高", "slogan": "当爹高清版。"},
    "watchmen": {"primary": "动作/冒险", "sub": "清版动作", "vibe": "黑暗超级英雄", "intensity": "中", "slogan": "守望者宇宙里揍人。"},
    "f.e.a.r.": {"primary": "射击 (FPS/TPS)", "sub": "恐怖FPS", "vibe": "黑暗/恐怖", "intensity": "高", "slogan": "子弹时间与红衣小女孩。"},
    "batman: arkham": {"primary": "动作/冒险", "sub": "开放世界动作", "vibe": "黑暗超级英雄", "intensity": "中", "slogan": "老爷揍人，拳拳到肉。"},
    "batman™: arkham knight": {"primary": "动作/冒险", "sub": "开放世界动作", "vibe": "黑暗超级英雄", "intensity": "中", "slogan": "蝙蝠车比蝙蝠侠还能打。"},
    "batman™: arkham origins": {"primary": "动作/冒险", "sub": "开放世界动作", "vibe": "黑暗超级英雄", "intensity": "中", "slogan": "年轻老爷的圣诞夜加班。"},
    "sniper elite": {"primary": "射击 (FPS/TPS)", "sub": "狙击潜行", "vibe": "二战写实", "intensity": "中", "slogan": "一枪一个，慢镜头爆蛋。"},
    "shank 2": {"primary": "动作/冒险", "sub": "横版清版", "vibe": "硬核暴力", "intensity": "中", "slogan": "二代继续刀刀见血。"},
    "xcom: enemy unknown": {"primary": "策略/模拟", "sub": "回合制战术", "vibe": "硬核策略", "intensity": "高", "slogan": "99%命中打偏，血压拉满。"},
    "xcom 2": {"primary": "策略/模拟", "sub": "回合制战术", "vibe": "反抗军硬核", "intensity": "高", "slogan": "游击队模拟器，顺便救地球。"},
    "xcom: chimera squad": {"primary": "策略/模拟", "sub": "回合制战术", "vibe": "小队叙事", "intensity": "中", "slogan": "外星人警察局模拟器。"},
    "hitman: absolution": {"primary": "动作/冒险", "sub": "潜行暗杀", "vibe": "冷静算计", "intensity": "中", "slogan": "光头再就业。"},
    "hitman: sniper challenge": {"primary": "射击 (FPS/TPS)", "sub": "狙击", "vibe": "冷静", "intensity": "中", "slogan": "狙击小游戏。"},
    "eets munchies": {"primary": "解谜/休闲", "sub": "物理解谜", "vibe": "轻松搞怪", "intensity": "低", "slogan": "喂饱怪物的益智小游戏。"},
    "din's curse": {"primary": "角色扮演 (RPG)", "sub": "动作RPG/地牢", "vibe": "复古硬核", "intensity": "中", "slogan": "地牢刷刷刷。"},
    "don't starve": {"primary": "策略/模拟", "sub": "生存建造", "vibe": "黑暗哥特", "intensity": "中", "slogan": "别饿死，顺便别疯。"},
    "don't starve together": {"primary": "策略/模拟", "sub": "生存建造", "vibe": "黑暗哥特", "intensity": "中", "slogan": "一起饿死，双倍快乐。"},
    "3dmark": {"primary": "策略/模拟", "sub": "基准测试", "vibe": "工具向", "intensity": "低", "slogan": "跑分用的，不是游戏。"},
    "euro truck simulator": {"primary": "策略/模拟", "sub": "驾驶模拟", "vibe": "解压/治愈", "intensity": "低", "slogan": "开卡车听电台，电子榨菜。"},
    "american truck simulator": {"primary": "策略/模拟", "sub": "驾驶模拟", "vibe": "解压/治愈", "intensity": "低", "slogan": "在美国开卡车。"},
    "baldur's gate": {"primary": "角色扮演 (RPG)", "sub": "CRPG", "vibe": "史诗奇幻", "intensity": "高", "slogan": "龙与地下城，掷骰子定生死。"},
    "baldur's gate ii": {"primary": "角色扮演 (RPG)", "sub": "CRPG", "vibe": "史诗奇幻", "intensity": "高", "slogan": "二代更史诗。"},
    "baldur's gate 3": {"primary": "角色扮演 (RPG)", "sub": "CRPG", "vibe": "史诗奇幻", "intensity": "高", "slogan": "掷骰子谈恋爱打怪三不误。"},
    "broken age": {"primary": "解谜/休闲", "sub": "点击冒险", "vibe": "独立/叙事", "intensity": "低", "slogan": "双线叙事，解谜看故事。"},
    "mad max": {"primary": "动作/冒险", "sub": "开放世界动作", "vibe": "废土狂野", "intensity": "中", "slogan": "废土飙车揍人。"},
    "sherlock holmes": {"primary": "解谜/休闲", "sub": "侦探推理", "vibe": "维多利亚悬疑", "intensity": "中", "slogan": "当福尔摩斯破案。"},
    "middle-earth™: shadow of mordor": {"primary": "动作/冒险", "sub": "开放世界动作", "vibe": "史诗黑暗", "intensity": "中", "slogan": "魔多割草与宿敌系统。"},
    "middle-earth™: shadow of war": {"primary": "动作/冒险", "sub": "开放世界动作", "vibe": "史诗黑暗", "intensity": "中", "slogan": "建兽人军团打兽人。"},
    "injustice": {"primary": "动作/冒险", "sub": "格斗", "vibe": "超级英雄", "intensity": "中", "slogan": "DC英雄互殴。"},
    "injustice™ 2": {"primary": "动作/冒险", "sub": "格斗", "vibe": "超级英雄", "intensity": "中", "slogan": "超人揍蝙蝠侠第二季。"},
    "invisible, inc.": {"primary": "策略/模拟", "sub": "回合制潜行", "vibe": "赛博朋克", "intensity": "高", "slogan": "间谍潜行回合制，一步错满盘输。"},
    "assetto corsa": {"primary": "策略/模拟", "sub": "拟真竞速", "vibe": "硬核模拟", "intensity": "高", "slogan": "方向盘玩家的归宿。"},
    "talisman": {"primary": "策略/模拟", "sub": "桌游改编", "vibe": "奇幻冒险", "intensity": "中", "slogan": "骰子桌游电子版。"},
    "crypt of the necrodancer": {"primary": "独立/叙事", "sub": "节奏地牢", "vibe": "魔性上头", "intensity": "高", "slogan": "跟着节拍踩格子，脚滑就死。"},
    "go! go! nippon!": {"primary": "独立/叙事", "sub": "视觉小说/旅游", "vibe": "轻松治愈", "intensity": "低", "slogan": "日本旅游宣传片。"},
    "this war of mine": {"primary": "策略/模拟", "sub": "生存模拟", "vibe": "黑暗沉重", "intensity": "中", "slogan": "战争里当平民，道德选择题。"},
    "100% orange juice": {"primary": "解谜/休闲", "sub": "桌游/大富翁", "vibe": "轻松搞怪", "intensity": "低", "slogan": "骰子互坑，友情破裂。"},
    "metro 2033": {"primary": "射击 (FPS/TPS)", "sub": "生存FPS", "vibe": "末世黑暗", "intensity": "高", "slogan": "地铁里打变异体，省子弹。"},
    "metro: last light": {"primary": "射击 (FPS/TPS)", "sub": "生存FPS", "vibe": "末世黑暗", "intensity": "高", "slogan": "地铁续集，继续省子弹。"},
    "metro exodus": {"primary": "射击 (FPS/TPS)", "sub": "生存FPS", "vibe": "末世史诗", "intensity": "高", "slogan": "走出地铁，荒野求生。"},
    "metro exodus enhanced": {"primary": "射击 (FPS/TPS)", "sub": "生存FPS", "vibe": "末世史诗", "intensity": "高", "slogan": "光追版地铁出地表。"},
    "sid meier's civilization vi": {"primary": "策略/模拟", "sub": "4X回合策略", "vibe": "史诗策略", "intensity": "高", "slogan": "再来一回合就天亮。"},
    "bulwark: falconeer chronicles": {"primary": "策略/模拟", "sub": "建造策略", "vibe": "奇幻飞行", "intensity": "中", "slogan": "建城堡开飞龙。"},
    "armello": {"primary": "策略/模拟", "sub": "桌游/回合策略", "vibe": "奇幻动物", "intensity": "中", "slogan": "动物王国夺王位。"},
    "the witcher 3": {"primary": "角色扮演 (RPG)", "sub": "开放世界RPG", "vibe": "黑暗奇幻史诗", "intensity": "高", "slogan": "打桩与打怪，昆特牌才是本体。"},
    "for honor": {"primary": "动作/冒险", "sub": "冷兵器对战", "vibe": "硬核格斗", "intensity": "高", "slogan": "格挡破防，心态破防。"},
    "mortal kombat": {"primary": "动作/冒险", "sub": "格斗", "vibe": "血腥暴力", "intensity": "中", "slogan": "爆头掏心，少儿不宜。"},
    "mortal kombat x": {"primary": "动作/冒险", "sub": "格斗", "vibe": "血腥暴力", "intensity": "中", "slogan": "真人快打X，更血腥。"},
    "mortal kombat 11": {"primary": "动作/冒险", "sub": "格斗", "vibe": "血腥暴力", "intensity": "中", "slogan": "终结技比剧情精彩。"},
    "spellforce": {"primary": "策略/模拟", "sub": "RTS+RPG混合", "vibe": "奇幻史诗", "intensity": "高", "slogan": "即时战略加英雄RPG。"},
    "strange brigade": {"primary": "射击 (FPS/TPS)", "sub": "合作射击", "vibe": "复古冒险", "intensity": "中", "slogan": "打木乃伊的爆米花片。"},
    "fahrenheit: indigo prophecy": {"primary": "独立/叙事", "sub": "互动电影", "vibe": "悬疑超自然", "intensity": "中", "slogan": "QTE演电影。"},
    "suicide squad: kill the justice league": {"primary": "动作/冒险", "sub": "合作射击", "vibe": "超级反派", "intensity": "中", "slogan": "组团杀正义联盟。"},
    "eden*": {"primary": "独立/叙事", "sub": "视觉小说", "vibe": "催泪治愈", "intensity": "低", "slogan": "短而美的末日恋爱。"},
    "icewind dale": {"primary": "角色扮演 (RPG)", "sub": "CRPG", "vibe": "史诗奇幻", "intensity": "高", "slogan": "冰风谷地牢团。"},
    "frostpunk": {"primary": "策略/模拟", "sub": "生存建造", "vibe": "黑暗末世", "intensity": "高", "slogan": "刁民与锅炉，二选一。"},
    "if my heart had wings": {"primary": "独立/叙事", "sub": "视觉小说", "vibe": "青春治愈", "intensity": "低", "slogan": "开滑翔翼谈恋爱。"},
    "mythforce": {"primary": "动作/冒险", "sub": "合作清版", "vibe": "复古卡通", "intensity": "中", "slogan": "80年代动画风合作闯关。"},
    "total war: warhammer": {"primary": "策略/模拟", "sub": "大战略+即时战斗", "vibe": "黑暗奇幻史诗", "intensity": "高", "slogan": "战锤全战，千小时起步。"},
    "total war: warhammer ii": {"primary": "策略/模拟", "sub": "大战略+即时战斗", "vibe": "黑暗奇幻史诗", "intensity": "高", "slogan": "二代更多派系更多肝。"},
    "total war: warhammer iii": {"primary": "策略/模拟", "sub": "大战略+即时战斗", "vibe": "黑暗奇幻史诗", "intensity": "高", "slogan": "三代震旦与混沌。"},
    "kona": {"primary": "冒险", "sub": "叙事冒险", "vibe": "寒冷悬疑", "intensity": "低", "slogan": "加拿大冬天探案。"},
    "hot lava": {"primary": "动作/冒险", "sub": "平台跑酷", "vibe": "轻松搞怪", "intensity": "中", "slogan": "地板是岩浆。"},
    "hearts of iron iv": {"primary": "策略/模拟", "sub": "大战略", "vibe": "硬核历史", "intensity": "高", "slogan": "二战模拟器，填线师模拟器。"},
    "grip: combat racing": {"primary": "策略/模拟", "sub": "科幻竞速", "vibe": "爽快刺激", "intensity": "中", "slogan": "反重力赛车揍人。"},
    "danganronpa": {"primary": "独立/叙事", "sub": "推理+视觉小说", "vibe": "绝望学园", "intensity": "中", "slogan": "互相残杀加学级裁判。"},
    "danganronpa 2": {"primary": "独立/叙事", "sub": "推理+视觉小说", "vibe": "绝望学园", "intensity": "中", "slogan": "二代换个岛继续杀。"},
    "danganronpa v3": {"primary": "独立/叙事", "sub": "推理+视觉小说", "vibe": "绝望学园", "intensity": "中", "slogan": "V3把 meta 玩到飞起。"},
    "danganronpa another episode": {"primary": "动作/冒险", "sub": "第三人称射击", "vibe": "绝望学园外传", "intensity": "中", "slogan": "弹丸外传，打黑白熊。"},
    "rwby": {"primary": "动作/冒险", "sub": "清版动作", "vibe": "动漫风格", "intensity": "中", "slogan": "RWBY 世界观揍怪。"},
    "deliver us the moon": {"primary": "冒险", "sub": "科幻叙事", "vibe": "孤独太空", "intensity": "中", "slogan": "月球打工救地球。"},
    "wallpaper engine": {"primary": "解谜/休闲", "sub": "桌面美化", "vibe": "工具向", "intensity": "低", "slogan": "动态壁纸，不是游戏。"},
    "divinity: original sin 2": {"primary": "角色扮演 (RPG)", "sub": "CRPG", "vibe": "奇幻策略", "intensity": "高", "slogan": "回合制CRPG天花板之一。"},
    "drawful 2": {"primary": "解谜/休闲", "sub": "派对猜画", "vibe": "轻松搞怪", "intensity": "低", "slogan": "你画我猜互坑。"},
    "oxygen not included": {"primary": "策略/模拟", "sub": "生存建造", "vibe": "硬核模拟", "intensity": "高", "slogan": "小人别缺氧别饿别崩。"},
    "the deed": {"primary": "独立/叙事", "sub": "短篇推理", "vibe": "黑色幽默", "intensity": "低", "slogan": "小体量谋杀解谜。"},
    "caveman world": {"primary": "策略/模拟", "sub": "文明建设", "vibe": "搞怪", "intensity": "中", "slogan": "原始人建文明。"},
    "planescape: torment": {"primary": "角色扮演 (RPG)", "sub": "CRPG", "vibe": "哲学奇幻", "intensity": "高", "slogan": "What can change the nature of a man?"},
    "northgard": {"primary": "策略/模拟", "sub": "RTS", "vibe": "北欧神话", "intensity": "中", "slogan": "维京人占格子打怪。"},
    "warhammer 40,000: gladius": {"primary": "策略/模拟", "sub": "4X回合", "vibe": "战锤40K", "intensity": "高", "slogan": "40K 回合制打架。"},
    "along the edge": {"primary": "独立/叙事", "sub": "视觉小说", "vibe": "选择叙事", "intensity": "低", "slogan": "选择决定命运。"},
    "martha is dead": {"primary": "独立/叙事", "sub": "心理恐怖", "vibe": "黑暗/恐怖", "intensity": "高", "slogan": "二战意大利的黑暗秘密。"},
    "crown champion": {"primary": "策略/模拟", "sub": "回合策略", "vibe": "奇幻", "intensity": "中", "slogan": "竞技场策略。"},
    "victoria 3": {"primary": "策略/模拟", "sub": "大战略", "vibe": "历史模拟", "intensity": "高", "slogan": "维多利亚时代模拟器。"},
    "warhammer: vermintide 2": {"primary": "动作/冒险", "sub": "合作清版", "vibe": "黑暗奇幻", "intensity": "高", "slogan": "四人组队砍鼠人。"},
    "just ignore them": {"primary": "独立/叙事", "sub": "恐怖/心理", "vibe": "诡异", "intensity": "中", "slogan": "别理它们。"},
    "dead in vinland": {"primary": "策略/模拟", "sub": "生存管理", "vibe": "北欧生存", "intensity": "中", "slogan": "维京荒岛求生。"},
    "monster hunter: world": {"primary": "动作/冒险", "sub": "共斗狩猎", "vibe": "史诗共斗", "intensity": "高", "slogan": "磨刀砍龙，一百小时入门。"},
    "monster hunter wilds": {"primary": "动作/冒险", "sub": "共斗狩猎", "vibe": "史诗共斗", "intensity": "高", "slogan": "新一代猎人，继续砍龙。"},
    "hunt: showdown": {"primary": "射击 (FPS/TPS)", "sub": "大逃杀+ PvPvE", "vibe": "黑暗西部", "intensity": "高", "slogan": "猎怪顺便猎玩家。"},
    "valfaris": {"primary": "动作/冒险", "sub": "横版射击", "vibe": "金属科幻", "intensity": "中", "slogan": "横版金属风射爆。"},
    "griftlands": {"primary": "策略/模拟", "sub": "卡牌RPG", "vibe": "赛博朋克", "intensity": "中", "slogan": "打牌谈判双系统。"},
    "disco elysium": {"primary": "角色扮演 (RPG)", "sub": "CRPG/叙事", "vibe": "颓废哲学", "intensity": "中", "slogan": "酗酒侦探与脑中二十四个人格。"},
    "my time at portia": {"primary": "策略/模拟", "sub": "经营模拟", "vibe": "治愈种田", "intensity": "低", "slogan": "3D 版星露谷造东西。"},
    "zombie army 4": {"primary": "射击 (FPS/TPS)", "sub": "合作射击", "vibe": "僵尸纳粹", "intensity": "中", "slogan": "狙击僵尸海。"},
    "evil genius 2": {"primary": "策略/模拟", "sub": "经营模拟", "vibe": "反派基地", "intensity": "中", "slogan": "当邪恶天才建基地。"},
    "neverwinter nights": {"primary": "角色扮演 (RPG)", "sub": "CRPG", "vibe": "龙与地下城", "intensity": "高", "slogan": "D&D 经典电子版。"},
    "mercury fallen": {"primary": "策略/模拟", "sub": "基地建造", "vibe": "科幻", "intensity": "中", "slogan": "外星基地经营。"},
    "postal 4": {"primary": "动作/冒险", "sub": "黑色幽默射击", "vibe": "恶搞暴力", "intensity": "中", "slogan": "美国疯子模拟器。"},
    "chinese parents": {"primary": "策略/模拟", "sub": "养成模拟", "vibe": "本土共鸣", "intensity": "低", "slogan": "当中国式家长。"},
    "a sky full of stars": {"primary": "独立/叙事", "sub": "视觉小说", "vibe": "恋爱治愈", "intensity": "低", "slogan": "星空下谈恋爱。"},
    "blasphemous": {"primary": "动作/冒险", "sub": "银河恶魔城", "vibe": "黑暗宗教", "intensity": "高", "slogan": "宗教受难与刀刀见血。"},
    "the scroll of taiwu": {"primary": "角色扮演 (RPG)", "sub": "武侠沙盒", "vibe": "武侠江湖", "intensity": "高", "slogan": "太吾绘卷，逆练内功。"},
    "super lucky's tale": {"primary": "动作/冒险", "sub": "3D平台", "vibe": "轻松卡通", "intensity": "低", "slogan": "可爱狐狸闯关。"},
    "new super lucky's tale": {"primary": "动作/冒险", "sub": "3D平台", "vibe": "轻松卡通", "intensity": "低", "slogan": "可爱狐狸闯关加强版。"},
    "mark of the ninja": {"primary": "动作/冒险", "sub": "横版潜行", "vibe": "忍者暗杀", "intensity": "中", "slogan": "横版潜行天花板。"},
    "anno 1800": {"primary": "策略/模拟", "sub": "城建模拟", "vibe": "工业时代", "intensity": "高", "slogan": "造岛贸易，肝到天明。"},
    "back 4 blood": {"primary": "射击 (FPS/TPS)", "sub": "合作射击", "vibe": "僵尸末世", "intensity": "高", "slogan": "精神续作，四人打怪。"},
    "brok the investigator": {"primary": "解谜/休闲", "sub": "点击冒险", "vibe": "动物侦探", "intensity": "低", "slogan": "鳄鱼侦探破案。"},
    "heavy rain": {"primary": "独立/叙事", "sub": "互动电影", "vibe": "悬疑沉重", "intensity": "中", "slogan": "折纸杀手与父亲们的选择。"},
    "beyond: two souls": {"primary": "独立/叙事", "sub": "互动电影", "vibe": "超自然叙事", "intensity": "中", "slogan": "灵异少女的人生电影。"},
    "autonauts": {"primary": "策略/模拟", "sub": "自动化建造", "vibe": "编程解压", "intensity": "低", "slogan": "教机器人种地。"},
    "streets of rage 4": {"primary": "动作/冒险", "sub": "横版清版", "vibe": "复古爽快", "intensity": "中", "slogan": "怒之铁拳，拳头说话。"},
    "the vale": {"primary": "动作/冒险", "sub": "无障碍动作", "vibe": "听觉叙事", "intensity": "中", "slogan": "盲人主角的动作冒险。"},
    "chernobylite": {"primary": "射击 (FPS/TPS)", "sub": "生存FPS", "vibe": "切尔诺贝利恐怖", "intensity": "高", "slogan": "切尔诺贝利打怪谈恋爱。"},
    "the expression amrilato": {"primary": "独立/叙事", "sub": "视觉小说+语言", "vibe": "治愈学习", "intensity": "低", "slogan": "学世界语谈恋爱。"},
    "paper dolls": {"primary": "独立/叙事", "sub": "恐怖解谜", "vibe": "中式恐怖", "intensity": "高", "slogan": "中式恐怖氛围。"},
    "the signifier": {"primary": "解谜/休闲", "sub": "意识解谜", "vibe": "赛博朋克哲学", "intensity": "中", "slogan": "潜入意识找真相。"},
    "figment 2": {"primary": "动作/冒险", "sub": "动作解谜", "vibe": "治愈童话", "intensity": "低", "slogan": "大脑里的音乐冒险。"},
    "baldur's gate 3": {"primary": "角色扮演 (RPG)", "sub": "CRPG", "vibe": "史诗奇幻", "intensity": "高", "slogan": "掷骰子谈恋爱打怪三不误。"},
    "fall guys": {"primary": "解谜/休闲", "sub": "派对竞速", "vibe": "轻松搞怪", "intensity": "低", "slogan": "糖豆人闯关，笑死算工伤。"},
    "war mongrels": {"primary": "策略/模拟", "sub": "即时战术", "vibe": "二战潜行", "intensity": "中", "slogan": "二战小队潜行。"},
    "asterix": {"primary": "动作/冒险", "sub": "清版/冒险", "vibe": "法式漫画", "intensity": "低", "slogan": "高卢英雄揍罗马人。"},
    "chicory: a colorful tale": {"primary": "动作/冒险", "sub": "绘画冒险", "vibe": "治愈治愈", "intensity": "低", "slogan": "给世界涂色与治愈。"},
    "snowtopia": {"primary": "策略/模拟", "sub": "滑雪场经营", "vibe": "轻松模拟", "intensity": "低", "slogan": "造滑雪场当老板。"},
    "wild terra 2": {"primary": "策略/模拟", "sub": "MMO生存建造", "vibe": "中世纪", "intensity": "中", "slogan": "中世纪沙盒建城。"},
    "the falconeer": {"primary": "动作/冒险", "sub": "飞行射击", "vibe": "奇幻空战", "intensity": "中", "slogan": "骑大鸟打架。"},
    "beyond a steel sky": {"primary": "解谜/休闲", "sub": "点击冒险", "vibe": "赛博朋克", "intensity": "中", "slogan": "钢铁天空下续作解谜。"},
    "i was a teenage exocolonist": {"primary": "独立/叙事", "sub": "养成+卡牌叙事", "vibe": "科幻成长", "intensity": "中", "slogan": "外星殖民地长大与选择。"},
    "the lamplighters league": {"primary": "策略/模拟", "sub": "回合战术", "vibe": "复古冒险", "intensity": "中", "slogan": "1930 年代小队战术。"},
    "bright memory: infinite": {"primary": "射击 (FPS/TPS)", "sub": "动作FPS", "vibe": "爽快科幻", "intensity": "高", "slogan": "短小精悍的刀枪剑戟FPS。"},
    "pathfinder: wrath of the righteous": {"primary": "角色扮演 (RPG)", "sub": "CRPG", "vibe": "史诗奇幻", "intensity": "高", "slogan": "正义之怒，神话道途。"},
    "one gun guy": {"primary": "射击 (FPS/TPS)", "sub": " roguelike 射击", "vibe": "极简硬核", "intensity": "高", "slogan": "一把枪闯关。"},
    "a space for the unbound": {"primary": "独立/叙事", "sub": "像素叙事", "vibe": "治愈青春", "intensity": "低", "slogan": "印尼小镇与超自然治愈。"},
    "paleo pines": {"primary": "策略/模拟", "sub": "农场模拟", "vibe": "治愈恐龙", "intensity": "低", "slogan": "养恐龙种田。"},
    "detroit: become human": {"primary": "独立/叙事", "sub": "互动电影", "vibe": "赛博朋克伦理", "intensity": "中", "slogan": "仿生人有没有灵魂。"},
    "the sims™ 4": {"primary": "策略/模拟", "sub": "生活模拟", "vibe": "过家家", "intensity": "低", "slogan": "电子过家家。"},
    "bang-on balls: chronicles": {"primary": "动作/冒险", "sub": "3D平台收集", "vibe": "轻松搞怪", "intensity": "低", "slogan": "球球闯关捡东西。"},
    "ad infinitum": {"primary": "冒险", "sub": "恐怖生存", "vibe": "一战恐怖", "intensity": "高", "slogan": "战壕里的噩梦。"},
    "sonic frontiers": {"primary": "动作/冒险", "sub": "开放世界跑酷", "vibe": "速度感", "intensity": "中", "slogan": "音速小子跑大地图。"},
    "terraformers": {"primary": "策略/模拟", "sub": "火星殖民", "vibe": "科幻策略", "intensity": "中", "slogan": "火星造地化。"},
    "lair land story": {"primary": "策略/模拟", "sub": "地牢经营", "vibe": "龙与地下城", "intensity": "中", "slogan": "地牢当老板。"},
    "this means warp": {"primary": "策略/模拟", "sub": " roguelike 太空", "vibe": "合作策略", "intensity": "中", "slogan": "飞船 roguelike 合作。"},
    "mind over magic": {"primary": "策略/模拟", "sub": "魔法学院建造", "vibe": "奇幻经营", "intensity": "中", "slogan": "建魔法学校养学生。"},
    "destroyer: the u-boat hunter": {"primary": "策略/模拟", "sub": "潜艇模拟", "vibe": "二战拟真", "intensity": "高", "slogan": "当驱逐舰猎潜艇。"},
    "remnant ii": {"primary": "射击 (FPS/TPS)", "sub": "魂系射击", "vibe": "黑暗科幻", "intensity": "高", "slogan": "打枪版黑魂。"},
    "tiny tina's wonderlands": {"primary": "射击 (FPS/TPS)", "sub": "刷宝射击", "vibe": "无厘头奇幻", "intensity": "中", "slogan": "无主之地味龙与地下城。"},
    "rollerdrome": {"primary": "动作/冒险", "sub": "轮滑射击", "vibe": "复古未来", "intensity": "高", "slogan": "滑旱冰射爆。"},
    "gori: cuddly carnage": {"primary": "动作/冒险", "sub": "动作砍杀", "vibe": "可爱暴力", "intensity": "中", "slogan": "可爱风砍怪。"},
    "wrestledunk sports": {"primary": "动作/冒险", "sub": "体育搞怪", "vibe": "轻松", "intensity": "低", "slogan": "摔角篮球大乱斗。"},
    "fashion police squad": {"primary": "射击 (FPS/TPS)", "sub": "搞笑FPS", "vibe": "无厘头", "intensity": "中", "slogan": "用服装纠正路人审美。"},
    "wolfstride": {"primary": "策略/模拟", "sub": "机甲回合+经营", "vibe": "西部机甲", "intensity": "中", "slogan": "开机甲打黑拳养狗。"},
    "lacuna": {"primary": "解谜/休闲", "sub": "侦探解谜", "vibe": "科幻 noir", "intensity": "中", "slogan": "科幻侦探选结局。"},
    "frail hearts": {"primary": "角色扮演 (RPG)", "sub": "JRPG", "vibe": "黑暗奇幻", "intensity": "中", "slogan": "黑暗向回合RPG。"},
    "botany manor": {"primary": "解谜/休闲", "sub": "园艺解谜", "vibe": "治愈", "intensity": "低", "slogan": "庄园里解谜养花。"},
    "gal*gun": {"primary": "射击 (FPS/TPS)", "sub": "恋爱射击", "vibe": "宅向搞笑", "intensity": "低", "slogan": "射中少女心。"},
    "the bookwalker": {"primary": "冒险", "sub": "叙事解谜", "vibe": "书中世界", "intensity": "中", "slogan": "进书里偷东西。"},
    "godlike burger": {"primary": "策略/模拟", "sub": "经营模拟", "vibe": "黑色幽默", "intensity": "中", "slogan": "外星开汉堡店用人肉。"},
    "song of farca": {"primary": "解谜/休闲", "sub": "黑客侦探", "vibe": "赛博朋克", "intensity": "中", "slogan": "当黑客侦探破案。"},
    "needy streamer overload": {"primary": "独立/叙事", "sub": "模拟+叙事", "vibe": "病娇直播", "intensity": "中", "slogan": "养病娇主播，小心坏结局。"},
    "initial drift online": {"primary": "策略/模拟", "sub": "漂移竞速", "vibe": "街机", "intensity": "中", "slogan": "漂移竞速网游。"},
    "intravenous": {"primary": "动作/冒险", "sub": "俯视角潜行", "vibe": "硬核潜行", "intensity": "高", "slogan": "俯视角潜行射杀。"},
    "symphony of war": {"primary": "策略/模拟", "sub": "战棋", "vibe": "奇幻史诗", "intensity": "高", "slogan": "大兵团战棋。"},
    "gotham knights": {"primary": "动作/冒险", "sub": "开放世界动作", "vibe": "蝙蝠家族", "intensity": "中", "slogan": "蝙蝠侠死了，换蝙蝠崽子们上班。"},
    "settlement survival": {"primary": "策略/模拟", "sub": "生存建造", "vibe": "殖民生存", "intensity": "中", "slogan": "殖民地从零建起。"},
    "toy tinker simulator": {"primary": "策略/模拟", "sub": "修理模拟", "vibe": "解压", "intensity": "低", "slogan": "修玩具模拟器。"},
    "the pegasus expedition": {"primary": "策略/模拟", "sub": "4X叙事", "vibe": "科幻史诗", "intensity": "高", "slogan": "星际远征做选择。"},
    "blacktail": {"primary": "动作/冒险", "sub": "开放世界动作", "vibe": "黑暗童话", "intensity": "中", "slogan": "当芭芭雅嘎射箭。"},
    "pocket bravery": {"primary": "动作/冒险", "sub": "格斗", "vibe": "像素复古", "intensity": "中", "slogan": "像素格斗。"},
    "the quarry": {"primary": "独立/叙事", "sub": "互动电影", "vibe": "B级恐怖", "intensity": "中", "slogan": "夏令营恐怖片你来选谁死。"},
    "spellforce: conquest of eo": {"primary": "策略/模拟", "sub": "回合策略", "vibe": "奇幻", "intensity": "高", "slogan": "魔法领主争霸。"},
    "metal slug tactics": {"primary": "策略/模拟", "sub": "回合战术", "vibe": "复古搞怪", "intensity": "中", "slogan": "合金弹头变战棋。"},
    "soundfall": {"primary": "动作/冒险", "sub": "节奏射击", "vibe": "音乐游戏", "intensity": "中", "slogan": "跟着节奏射爆。"},
    "bramble: the mountain king": {"primary": "冒险", "sub": "叙事平台", "vibe": "黑暗童话", "intensity": "中", "slogan": "北欧黑暗童话闯关。"},
    "who pressed mute on uncle marcus": {"primary": "独立/叙事", "sub": "互动电影", "vibe": "黑色喜剧", "intensity": "低", "slogan": "家庭聚会谋杀案。"},
    "shashingo": {"primary": "解谜/休闲", "sub": "摄影+语言学习", "vibe": "治愈", "intensity": "低", "slogan": "拍照学日语。"},
    "miasma chronicles": {"primary": "策略/模拟", "sub": "回合战术", "vibe": "末世科幻", "intensity": "中", "slogan": "末世回合战术。"},
    "karmazoo": {"primary": "解谜/休闲", "sub": "合作派对", "vibe": "治愈", "intensity": "低", "slogan": "合作闯关做善事。"},
    "age of wonders 4": {"primary": "策略/模拟", "sub": "4X奇幻", "vibe": "奇幻史诗", "intensity": "高", "slogan": "奇幻文明再一回合。"},
    "afterimage": {"primary": "动作/冒险", "sub": "银河恶魔城", "vibe": "手绘奇幻", "intensity": "高", "slogan": "美型银河城。"},
    "spirited thief": {"primary": "动作/冒险", "sub": "潜行", "vibe": "日式", "intensity": "中", "slogan": "忍者潜行偷东西。"},
    "soul stalker": {"primary": "动作/冒险", "sub": "魂系", "vibe": "黑暗", "intensity": "高", "slogan": "类魂动作。"},
    "arkanoid": {"primary": "解谜/休闲", "sub": "打砖块", "vibe": "复古", "intensity": "低", "slogan": "打砖块经久不衰。"},
    "castle of alchemists": {"primary": "策略/模拟", "sub": "塔防/建造", "vibe": "奇幻", "intensity": "中", "slogan": "炼金术士守城堡。"},
    "no more heroes 3": {"primary": "动作/冒险", "sub": "砍杀", "vibe": "无厘头", "intensity": "中", "slogan": "杀手打工买周边。"},
    "murders on the yangtze river": {"primary": "解谜/休闲", "sub": "侦探推理", "vibe": "民国悬疑", "intensity": "中", "slogan": "长江上的谋杀案。"},
    "smart factory tycoon": {"primary": "策略/模拟", "sub": "经营模拟", "vibe": "工业", "intensity": "中", "slogan": "智能工厂大亨。"},
    "super bullet break": {"primary": "策略/模拟", "sub": "卡牌 roguelike", "vibe": "宅向", "intensity": "中", "slogan": "美少女卡牌 roguelike。"},
    "gerda: a flame in winter": {"primary": "独立/叙事", "sub": "叙事RPG", "vibe": "二战丹麦", "intensity": "中", "slogan": "二战小镇里的选择。"},
    "topspin 2k25": {"primary": "策略/模拟", "sub": "网球模拟", "vibe": "体育", "intensity": "中", "slogan": "网球大满贯。"},
    "beneath oresa": {"primary": "策略/模拟", "sub": "卡牌 roguelike", "vibe": "赛博朋克", "intensity": "中", "slogan": "赛博卡牌地牢。"},
    "arc raiders": {"primary": "射击 (FPS/TPS)", "sub": "合作射击", "vibe": "科幻末世", "intensity": "高", "slogan": "打机械怪合作射击。"},
    "snufkin": {"primary": "解谜/休闲", "sub": "休闲冒险", "vibe": "治愈", "intensity": "低", "slogan": "姆明世界里的治愈散步。"},
    "nine sols": {"primary": "动作/冒险", "sub": "银河恶魔城", "vibe": "东方奇幻", "intensity": "高", "slogan": "东方风银河城，弹反爽。"},
    "naiad": {"primary": "解谜/休闲", "sub": "休闲探索", "vibe": "治愈", "intensity": "低", "slogan": "当水精灵在河里漂。"},
    "mirror 2": {"primary": "解谜/休闲", "sub": "三消+视觉小说", "vibe": "宅向", "intensity": "低", "slogan": "三消看剧情。"},
    "warhammer age of sigmar: realms of ruin": {"primary": "策略/模拟", "sub": "RTS", "vibe": "战锤西格玛", "intensity": "高", "slogan": "西格玛时代即时战略。"},
    "etrian odyssey": {"primary": "角色扮演 (RPG)", "sub": "DRPG", "vibe": "硬核地牢", "intensity": "高", "slogan": "画地图下地牢。"},
    "another crab's treasure": {"primary": "动作/冒险", "sub": "类魂", "vibe": "可爱硬核", "intensity": "高", "slogan": "螃蟹版黑魂，壳当盾。"},
    "autonauts vs piratebots": {"primary": "策略/模拟", "sub": "自动化建造", "vibe": "编程解压", "intensity": "低", "slogan": "机器人打海盗。"},
    "garden life": {"primary": "策略/模拟", "sub": "园艺模拟", "vibe": "治愈", "intensity": "低", "slogan": "种花造园子。"},
    "stray gods": {"primary": "独立/叙事", "sub": "音乐剧叙事", "vibe": "希腊神话", "intensity": "低", "slogan": "音乐剧版希腊神谈恋爱。"},
    "between horizons": {"primary": "冒险", "sub": "科幻叙事", "vibe": "太空飞船", "intensity": "中", "slogan": "飞船上查案。"},
    "spirittea": {"primary": "策略/模拟", "sub": "经营+生活", "vibe": "治愈", "intensity": "低", "slogan": "开澡堂招待灵魂。"},
    "lost skies": {"primary": "动作/冒险", "sub": "合作生存", "vibe": "空岛", "intensity": "中", "slogan": "空岛生存建造。"},
    "ingression": {"primary": "策略/模拟", "sub": "策略", "vibe": "科幻", "intensity": "中", "slogan": "科幻策略。"},
    "synergy": {"primary": "策略/模拟", "sub": "模拟", "vibe": "科幻", "intensity": "中", "slogan": "科幻模拟。"},
    "barro gt": {"primary": "策略/模拟", "sub": "竞速", "vibe": "拟真", "intensity": "中", "slogan": "巴罗GT竞速。"},
    "gatekeeper": {"primary": "策略/模拟", "sub": "塔防/策略", "vibe": "奇幻", "intensity": "中", "slogan": "守门人策略。"},
    "rungore": {"primary": "策略/模拟", "sub": "卡牌 roguelike", "vibe": "地牢", "intensity": "中", "slogan": "地牢卡牌爬塔。"},
    "kind words 2": {"primary": "解谜/休闲", "sub": "写信治愈", "vibe": "治愈", "intensity": "低", "slogan": "写温暖的话治愈彼此。"},
    "on your tail": {"primary": "冒险", "sub": "侦探", "vibe": "动物村", "intensity": "低", "slogan": "动物村侦探。"},
    "what the fog": {"primary": "动作/冒险", "sub": " roguelike", "vibe": "吸血鬼幸存者类", "intensity": "中", "slogan": "幸存者类割草。"},
    "ghostrunner 2": {"primary": "动作/冒险", "sub": "跑酷砍杀", "vibe": "赛博朋克", "intensity": "高", "slogan": "一刀死跑酷续作。"},
    "cobalt core": {"primary": "策略/模拟", "sub": "卡牌 roguelike", "vibe": "太空", "intensity": "中", "slogan": "太空卡牌 roguelike。"},
    "wizard of legend 2": {"primary": "动作/冒险", "sub": " roguelike", "vibe": "魔法地牢", "intensity": "高", "slogan": "法师地牢 roguelike。"},
    "63 days": {"primary": "独立/叙事", "sub": "叙事", "vibe": "生存", "intensity": "中", "slogan": "六十三天生存选择。"},
    "sucker for love: date to die for": {"primary": "独立/叙事", "sub": "恋爱+克苏鲁", "vibe": "邪典恋爱", "intensity": "中", "slogan": "和古神谈恋爱。"},
    "endless monday": {"primary": "独立/叙事", "sub": "叙事", "vibe": "职场", "intensity": "低", "slogan": "无限周一模拟器。"},
    "station to station": {"primary": "策略/模拟", "sub": "铁路拼图", "vibe": "解压", "intensity": "低", "slogan": "连铁路造景。"},
    "operation: polygon storm": {"primary": "策略/模拟", "sub": "塔防", "vibe": "多边形", "intensity": "中", "slogan": "多边形塔防。"},
    "everholm": {"primary": "策略/模拟", "sub": "建造", "vibe": "治愈", "intensity": "低", "slogan": "小岛建造治愈。"},
    "like a dragon gaiden": {"primary": "动作/冒险", "sub": "动作冒险", "vibe": "极道叙事", "intensity": "中", "slogan": "桐生一马隐姓埋名再就业。"},
    "nice day for fishing": {"primary": "解谜/休闲", "sub": "钓鱼", "vibe": "治愈", "intensity": "低", "slogan": "钓鱼摸鱼。"},
    "dungeon tycoon": {"primary": "策略/模拟", "sub": "地牢经营", "vibe": "奇幻", "intensity": "中", "slogan": "地牢大亨。"},
    "death in unison": {"primary": "独立/叙事", "sub": "叙事", "vibe": "黑暗", "intensity": "中", "slogan": " unison 中的死亡。"},
    "ecognomix": {"primary": "策略/模拟", "sub": "模拟", "vibe": "生态", "intensity": "中", "slogan": "生态模拟。"},
    "eco gnomix": {"primary": "策略/模拟", "sub": "模拟", "vibe": "生态", "intensity": "中", "slogan": "生态模拟。"},
    "servonauts": {"primary": "策略/模拟", "sub": "自动化", "vibe": "科幻", "intensity": "中", "slogan": "服务机器人经营。"},
    "little-known galaxy": {"primary": "策略/模拟", "sub": "太空", "vibe": "轻松", "intensity": "中", "slogan": "小宇宙探索。"},
    "tomb raider": {"primary": "动作/冒险", "sub": "冒险解谜", "vibe": "古墓探险", "intensity": "中", "slogan": "劳拉经典古墓探险。"},
    "summerhouse": {"primary": "解谜/休闲", "sub": "建造放松", "vibe": "治愈", "intensity": "低", "slogan": "搭小房子放松。"},
    "ad fundum": {"primary": "独立/叙事", "sub": "叙事RPG", "vibe": "轻松", "intensity": "低", "slogan": "轻松叙事RPG。"},
    "beholder: conductor": {"primary": "策略/模拟", "sub": "反乌托邦模拟", "vibe": "黑暗", "intensity": "中", "slogan": "当房东监视房客。"},
    "the jackbox megapicker": {"primary": "解谜/休闲", "sub": "派对工具", "vibe": "工具", "intensity": "低", "slogan": "派对游戏挑选器。"},
    "spin hero": {"primary": "角色扮演 (RPG)", "sub": "策略RPG", "vibe": "独立", "intensity": "中", "slogan": "旋转英雄策略。"},
    "ninjam!": {"primary": "解谜/休闲", "sub": "派对动作", "vibe": "轻松", "intensity": "低", "slogan": "同屏乱斗。"},
    "grid ranger": {"primary": "动作/冒险", "sub": "竞速", "vibe": "独立", "intensity": "中", "slogan": "网格竞速。"},
    "man i just wanna go home": {"primary": "解谜/休闲", "sub": "休闲", "vibe": "治愈", "intensity": "低", "slogan": "只想回家。"},
    "monster hunter wilds beta": {"primary": "动作/冒险", "sub": "共斗狩猎", "vibe": "史诗", "intensity": "高", "slogan": "野化测试服。"},
    "escape from tarkov": {"primary": "射击 (FPS/TPS)", "sub": "硬核大逃杀", "vibe": "硬核拟真", "intensity": "高", "slogan": "跑刀与心跳，拟真到自闭。"},
    "petz catz": {"primary": "策略/模拟", "sub": "宠物模拟", "vibe": "轻松", "intensity": "低", "slogan": "养猫模拟。"},
    "skillshot city": {"primary": "动作/冒险", "sub": "体育", "vibe": "街头", "intensity": "中", "slogan": "街头技巧球。"},
    "movavi video suite": {"primary": "策略/模拟", "sub": "实用工具", "vibe": "工具", "intensity": "低", "slogan": "视频编辑软件，非游戏。"},
    "postal: brain damaged": {"primary": "射击 (FPS/TPS)", "sub": "复古FPS", "vibe": "恶搞", "intensity": "中", "slogan": "POSTAL 复古射爆。"},
    "immortality": {"primary": "独立/叙事", "sub": "互动电影", "vibe": "悬疑", "intensity": "中", "slogan": "剪片子找真相。"},
    "lego® 2k drive": {"primary": "策略/模拟", "sub": "竞速", "vibe": "乐高", "intensity": "低", "slogan": "乐高开车。"},
}

def normalize_name(name):
    return name.lower().strip()

def find_known(name):
    n = normalize_name(name)
    candidates = [(k, v) for k, v in KNOWN.items() if k in n]
    if not candidates:
        return None
    candidates.sort(key=lambda x: -len(x[0]))
    return {key: value.strip() for key, value in candidates[0][1].items()}

def primary_from_genres(genres):
    g = " ".join(genres).lower()
    if "射击" in g or "fps" in g or "tps" in g:
        return "射击 (FPS/TPS)"
    if "角色扮演" in g or "rpg" in g:
        return "角色扮演 (RPG)"
    if "策略" in g or "模拟" in g:
        return "策略/模拟"
    if "动作" in g or "冒险" in g:
        return "动作/冒险"
    if "解谜" in g or "休闲" in g:
        return "解谜/休闲"
    if "独立" in g:
        return "独立/叙事"
    return "动作/冒险"

def sub_from_name_and_genres(name, genres):
    n = normalize_name(name)
    g = " ".join(genres).lower()
    if "roguelike" in n or "肉鸽" in g or "roguelike" in g:
        return "肉鸽"
    if "souls" in n or "魂" in n or "soulslike" in n:
        return "类魂"
    if "metroidvania" in n or "银河" in g or "恶魔城" in g:
        return "银河恶魔城"
    if "模拟" in g or "经营" in g or "sim" in n:
        return "经营模拟"
    if "生存" in g or "don't starve" in n or "survival" in n:
        return "生存建造"
    if "塔防" in g or "tower" in n:
        return "塔防"
    if "卡牌" in g or "card" in n:
        return "卡牌"
    if "回合" in g or "turn" in n:
        return "回合策略/战术"
    if "格斗" in g or "fighting" in n:
        return "格斗"
    if "竞速" in g or "racing" in n:
        return "竞速"
    return "多种元素"

def vibe_from_genres(genres):
    g = " ".join(genres).lower()
    if "恐怖" in g or "horror" in g:
        return "黑暗/恐怖"
    if "策略" in g and "硬核" not in g:
        return "策略感"
    return "风格各异"

def intensity_from_genres(genres):
    g = " ".join(genres).lower()
    if "休闲" in g or "放松" in g:
        return "低"
    if "策略" in g or "模拟" in g:
        return "中"
    if "动作" in g or "射击" in g:
        return "高"
    return "中"

def slogan_fallback(name, primary):
    return f"《{name}》——{primary}，值得一试。"

def _classify_one(game):
    appid = game.get("appid")
    name = game.get("name", "")
    genres = game.get("genres") or []
    known = find_known(name)
    if known:
        return {
            "appid": str(appid),
            "name": name,
            "analysis": {
                "primary": known["primary"],
                "sub": known["sub"],
                "vibe": known["vibe"],
                "intensity": known["intensity"],
                "slogan": known["slogan"],
            }
        }
    primary = primary_from_genres(genres)
    sub = sub_from_name_and_genres(name, genres)
    vibe = vibe_from_genres(genres)
    intensity = intensity_from_genres(genres)
    slogan = slogan_fallback(name, primary)
    return {
        "appid": str(appid),
        "name": name,
        "analysis": {
            "primary": primary,
            "sub": sub,
            "vibe": vibe,
            "intensity": intensity,
            "slogan": slogan,
        }
    }

def classify_one(game, overrides=None):
    from classification_overrides import load_overrides, correction, evidence, MAIN_TO_PRIMARY
    overrides = load_overrides() if overrides is None else overrides
    result = _classify_one(game)
    rule = correction(game, overrides)
    if rule:
        result['analysis']['primary'] = MAIN_TO_PRIMARY[rule['main_category']]
        result['analysis'].update({k: rule[k] for k in ('sub', 'vibe', 'intensity', 'slogan') if k in rule})
        if 'slogan' not in rule and not find_known(game.get('name', '')):
            result['analysis']['slogan'] = slogan_fallback(game.get('name', ''), result['analysis']['primary'])
        result['classification_evidence'] = evidence(rule)
    else:
        result['classification_evidence'] = {'source': 'known_name' if find_known(game.get('name', '')) else 'genre_rules'}
    return result


def main():
    import argparse
    from pathlib import Path
    from steam_classification import add_selection_arguments, load_selected
    parser = argparse.ArgumentParser(description="按五维规则分类，默认仅选择明确的 game 类型")
    base = Path(__file__).resolve().parent
    parser.add_argument("-i", "--input", type=Path, default=base / INPUT_FILE)
    parser.add_argument("-o", "--output", type=Path, default=base / OUTPUT_FILE)
    add_selection_arguments(parser)
    args = parser.parse_args()
    try:
        games, selected = load_selected(args)
    except (OSError, ValueError) as exc:
        parser.exit(1, f"分类失败：{exc}\n")
    from classification_overrides import load_overrides
    try:
        overrides = load_overrides()
    except (OSError, ValueError):
        parser.exit(1, '分类失败：请检查 AppID 校正规则文件\n')
    out = [{**classify_one(g, overrides), "run_id": g.get("run_id")} for g in selected]
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"采集记录 {len(games)} 条，已分类 {len(out)} 条，结果已写入 {args.output}")

if __name__ == "__main__":
    main()
