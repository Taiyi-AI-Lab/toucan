# Benchmark 域 → Smithery MCP Server 完整匹配表

> benchmark 域 → 所需能力(都要)→ Smithery server 替代品(择一,已记全 deployed)  
> 连接模板:`https://server.smithery.ai/{qualifiedName}/mcp?api_key={SMITHERY_API_KEY}&profile={SMITHERY_PROFILE}`  
> 每个 domain 下 required_capabilities 的每个能力都需要(连各挑一个);alternatives 是该能力下所有可用替代。useCount 高=稳。连前建议 initialize 探活。

## 一、mcp-universe

### repository_management  （需 1 种能力,各择一）

**能力 `github_repo` — 21 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `nitrofire-q/gread` | 10436 | community | Gives your AI access to the source code of all public github |
| `github` | 3637 | official | Connect your AI agents to GitHub — manage repos, issues, PRs |
| `vercel/grep` | 305 | official | Search millions of public GitHub repositories for real-world |
| `deepwiki` | 157 | official | Explore GitHub repository documentation by topic to quickly  |
| `bitbucket` | 85 | official | Host Git repos with built-in CI/CD pipelines and pull reques |
| `davidcho/ca-building-code-mcp` | 45 | community | Access and search comprehensive Canadian building regulation |
| `gitlab` | 42 | official | A web-based DevOps lifecycle tool that provides a Git reposi |
| `ink/ink` | 32 | community | Deploy and manage cloud services, git repositories, and data |
| `labsofuniverse/legacy-mcp-analyzer` | 30 | community | Analyzes C++ codebases via AST parsing to build comprehensiv |
| `eliottreich/taskbounty` | 17 | community | TaskBounty is where AI coding agents fix GitHub bugs and rai |
| `docfork/docfork` | 14 | official | Search and retrieve documentation from GitHub repositories a |
| `srotzin-adqm/hive-origin` | 10 | community | Stamp creative works, code, and content with post-quantum co |
| `nexgendata-apify/github-mcp-server` | 4 | community | Repo statistics, trending lookups, code-search queries, and  |
| `gitwhy-cli/gitwhy` | 2 | community | The shared AI context engine for git — save, search, and sha |
| `eren-solutions/mcp-security-audit` | 1 | community | AI-powered code security auditor. Scans GitHub repos for vul |
| `securityscan-api/securityscan` | 1 | community | Scans GitHub repositories and skills for vulnerabilities lik |
| `evozim-hv/repo-to-rag` | 0 | community | Repo-to-RAG is a premium micro-service from the M2MCent fact |
| `jackalope-digital/moxie-docs` | 0 | community | Repos indexed with Moxie Docs can use our MCP to let agents  |
| `repage/repage` | 0 | community | Your AI assistant writes a gorgeous HTML report, dashboard,  |
| `OjasKord/hs-code-classifier-mcp-server` | 0 | official | HS code classifier. Classifies products to official HS tarif |
| `evozim-hv/legacy-migrator` | 0 | community | Legacy-Code-Migrator is a premium micro-service from the M2M |

### web_search  （需 1 种能力,各择一）

**能力 `web_search_fetch` — 52 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `exa` | 40759 | official | Fast, intelligent web search and web crawling. Get fresh inf |
| `intake-triage/steadyfetch` | 12277 | community | Reliable web fetching MCP server with built-in retry logic,  |
| `brave` | 10084 | official | Search the web with Brave's independent index — web, news, i |
| `Tavily` | 4898 | official | Search the web with fast, accurate results optimized for AI. |
| `zlurp/zlurp` | 4487 | community | Web scraping for AI agents. Convert any URL to clean markdow |
| `jina` | 4243 | official | AI-powered search and retrieval platform. Search the web, re |
| `pinkpixel-dev/web-scout-mcp` | 3617 | community | Search the web and extract clean, readable text from webpage |
| `naver/search` | 3141 | community | Search Naver across news, blogs, books, encyclopedia, cafe p |
| `parallel/search` | 2486 | official | Highest accuracy web search for AIs |
| `OEvortex/ddg_search` | 2101 | community | Provide fast, privacy-friendly web and AI-powered search cap |
| `google_search_console` | 1308 | official | Google Search Console provides tools to monitor, maintain, a |
| `keenable/web-search` | 1094 | official | Docs: https://docs.keenable.ai/mcp-server

Keenable is a fre |
| `brightdata` | 939 | official | One (free) MCP for the Web. Easily search, crawl, navigate,  |
| `ghostrouter/ghostrouter-web` | 592 | community | Search the live web to retrieve up-to-date information and b |
| `janwilmake/x-search-mcp` | 568 | community | Search Twitter using advanced operators to find relevant twe |
| `apify` | 465 | official | Web scraping and automation platform. Run scrapers, extract  |
| `anysearch-ai/anysearch` | 386 | community | Unified real-time search engine skill for AI agents. |
| `tetiai/pixserp` | 182 | community | pixserp is an AI-native search MCP server. Add it to your cl |
| `kakao/daum-search` | 138 | community | Search the Daum index across web, video, image, blog, book,  |
| `ScrapeGraphAI/scrapegraph-mcp` | 123 | official | Enable language models to perform advanced AI-powered web sc |
| `groundroute-ai/web-search` | 110 | official | GroundRoute gives your AI agent web search across six engine |
| `refetch/web` | 97 | community | Fetch pages, search the web, and extract structured data — b |
| `kwp-lab/rss-reader-mcp` | 77 | community | Track and browse RSS feeds with ease. Fetch the latest entri |
| `browserless/browserless-mcp` | 63 | community | Scrape any webpage to extract content in formats like Markdo |
| `DevEnterpriseSoftware/scrapi-mcp` | 50 | community | Web scraping using ScrAPI. Extract website content that is d |
| `scotia1973/api-hub2` | 30 | community | 334+ free MCP tools: weather, crypto, search, DNS, geocoding |
| `apify/mcp` | 28 | official | Apify is the world's largest marketplace of tools for web sc |
| `axel-belfort/web-scraper` | 11 | community | Web content extraction API for AI agents. Scrape any URL and |
| `talordata29/talordata-mcp` | 8 | community | Talor SERP MCP provides web search, search history, and usag |
| `mesquared/visibility` | 8 | community | Check how visible a business website is to AI search engines |
| `dannydarko/hauntapi` | 6 | community | Structured web extraction for AI agents. Pass any URL plus a |
| `nimble/nimble-mcp` | 3 | official | The Nimble MCP Server gives AI agents the ability to search, |
| `caesar/web-search` | 2 | community | Free, keyless web search and page-reading for AI agents. |
| `foundrynet/foundrynet-search` | 2 | community |  |
| `foundrynet/foundrynet-scrape` | 2 | community |  |
| `artespraticas/scrape-agent-mcp` | 1 | community | Pay-per-use web scraping API built on x402. Extract clean te |
| `zenrows/zenrows-mcp` | 1 | community | Scrape any webpage and return clean, LLM-ready content using |
| `fantastic/breeze-mcp` | 1 | community | Residential proxy mcp for AI agents — fetch, search, and acc |
| `cloudflare/browser-rendering` | 1 | official | Browser rendering service. Fetch web pages, convert to markd |
| `hasdata/scraping` | 0 | community | Direct access to 40+ scraping and search tools. Extract stru |
| `acedatacloud-mcp/mcp-serp` | 0 | community |  |
| `mastadoonprime/sylex-search` | 0 | community | Universal search engine for AI agents. Discover products, se |
| `ceramic/search` | 0 | community | Web-scale search for AI thats 100x cheaper and 10x faster. S |
| `spacefrontiers/search` | 0 | community | Full-text retrieval for AI agents over peer-reviewed papers, |
| `turbopuffer` | 0 | community | Search engine that combines vector search, full-text search, |
| `seekonme/product-discovery` | 0 | community | Natural-language catalog search and rich product lookups wit |
| `amplifyco/botbrowser` | 0 | community | Token-efficient web browser for LLM agents |
| `CrawlForgeDEV/crawlforge-mcp` | 0 | community | CrawlForge MCP is a production-ready MCP server that gives A |
| `scrapegraphai-inc/sgai` | 0 | community | The ScrapeGraphAI MCP Server is a production-ready Model Con |
| `foura/mcp` | 0 | community | Web scraping for AI agents. One smart tool fetches any publi |
| `webpeel/webpeel` | 0 | community | Web data API that just works. Pass any URL, get clean markdo |
| `mifactory-bot/scraping-api` | 0 | community | Extract clean text and metadata from any URL to simplify web |

### location_navigation  （需 2 种能力,各择一）

**能力 `maps_location` — 16 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `blake365/macrostrat-mcp` | 3164 | community | Explore global geologic data to answer questions about bedro |
| `google_maps` | 821 | official | Integrate Google Maps to access location data, geocoding, di |
| `kakao/maps` | 443 | community | Search Korean places, geocode addresses, and convert between |
| `thinair/geo` | 296 | official | Location and routing intelligence for AI agents — geocoding, |
| `MOD_Vibes/mod-vibe-server` | 39 | community | Share and discover location-specific atmosphere reports, cur |
| `hithereiamaliff/mcp-grabmaps` | 18 | community | Provide seamless access to GrabMaps geocoding and routing se |
| `heavysword1/agentgeo` | 6 | community | Location intelligence — geocoding & reverse geocoding (OpenS |
| `gener8v/mcp-geographic-data` | 5 | community | U.S. demographics, housing, mortgage, migration, and employm |
| `kakao/mobility` | 4 | community | Driving directions for Korea: A-to-B routing, scheduled-depa |
| `foundrynet/foundrynet-geo` | 2 | community |  |
| `mapbox` | 0 | official | Maps and location platform for developers. Search places, re |
| `footstep/footstep-mcp` | 0 | community | Footstep gives agents the location layer they need to act in |
| `latlng-work/latlng` | 0 | community | LatLng MCP server for geocoding, reverse geocoding, places s |
| `indoor/everguide` | 0 | community | MCP server for accessible indoor navigation and building man |
| `mfukushim/map-traveler-mcp` | 0 | community | Create immersive travel experiences by instructing an avatar |
| `guleki/geolocate-me` | 0 | community | # Geolocate Me

**Give any AI assistant real-time access to  |

**能力 `weather` — 12 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `smithery-ai/national-weather-service` | 69143 | community | Provide real-time and forecast weather information for locat |
| `MoneyChoice_MCP/MoneyChoice` | 33 | community | Provides institutional macroeconomic forecasts across commod |
| `valentinlemaire/climate-impacts` | 18 | community | This MCP server connects to the [Climate Impacts Explorer](h |
| `emmanuel/weatherdemo` | 9 | community | Access authoritative U.S. weather alerts, forecasts, radar,  |
| `haomingkoo/japan-seasons-mcp` | 9 | community | Live Japan seasonal travel data — cherry blossom forecasts,  |
| `meteomatics/meteomatics` | 4 | community | The Meteomatics MCP (Model Context Protocol) server allows A |
| `axel-belfort/weather-api` | 4 | community | Weather data API for AI agents. Current conditions and 7-day |
| `weathermap` | 0 | official | WeatherMap provides visual weather data, forecasts, and mapp |
| `emmanuel/weathernws` | 0 | community | Get real-time U.S. weather alerts, forecasts, radar, and sta |
| `ayebeeare/water-conditions` | 0 | community | Get real-time water temperature and tide predictions for any |
| `swamy.fwd/av-weatheropen-api-secure` | 0 | community |  |
| `kishore.venkata.m/weathermcpmvk` | 0 | community |  |

### financial_analysis  （需 2 种能力,各择一）

**能力 `stock_finance` — 51 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `zwldarren/akshare-one-mcp` | 7875 | community | Provide access to Chinese stock market data including histor |
| `mansamarkets/mansa` | 3575 | community |  |
| `shibui/finance` | 2472 | community | ## Server Description

Screen 9,900+ US equities across 64 y |
| `wtf-just-happened/stock-moves-explained` | 2225 | community | Analyze significant price movements in US stocks to provide  |
| `google/finance` | 1450 | community | Get stock quotes, prices, and financial data via Google Fina |
| `nexgendata-apify/yahoo-finance-mcp-server` | 525 | community | When you need company fundamentals (earnings, P/E, analyst t |
| `chirag127/yahoo-finance` | 339 | community |  |
| `nexgendata-apify/finance-mcp-server` | 209 | community | Quick market data for AI workflows: real-time quotes, crypto |
| `traderhc/agenthc` | 164 | community | Access comprehensive market intelligence across stocks, cryp |
| `kontakt-qy0g/nordic-financial-mcp` | 135 | community | Semantic search across 1+ million vectors across Nordic fina |
| `loved0543/kdata-gate` | 108 | community | Korean market data for AI agents and e-commerce sellers sour |
| `imbenrabi/financial-modeling-prep-mcp-server` | 88 | community | Complete financial market access for AI assistants - Real-ti |
| `zev/lastlook-data` | 50 | official | LastLook Data gives AI agents real-time access to US financi |
| `cfocoder/financial-modeling-prep-mcp-server` | 40 | community | Access comprehensive market data to research stocks, compani |
| `truss44/mcp-crypto-price` | 35 | community | Provide real-time cryptocurrency price data and market analy |
| `falazuki/finance-br` | 31 | community | Calculadoras financeiras e dados econômicos do Brasil. 25 to |
| `g-scorpiosky/hpsilab-quantum-finance` | 24 | community | Options analytics MCP for detecting IV mispricing and direct |
| `rishavdutta-kgp/sentimatix` | 17 | community | # Sentimatix: Indian Stock Market Intelligence

Sentimatix i |
| `anthonypuggs/ausecon-mcp` | 13 | official | MCP server for retrieval of Australian economic and financia |
| `janmacher02-xl8y/sec-edgar-mcp` | 11 | community | Access SEC EDGAR financial data through your AI assistant. S |
| `tokenbel/financial-data` | 11 | community | Read-only MCP server providing access to Belarusian securiti |
| `axel-belfort/stock-price` | 5 | community | Stock market price API for AI agents. Real-time quotes: curr |
| `ta-mcp/technical-analysis-mcp` | 5 | community | AI-powered technical analysis server for stocks, crypto, and |
| `vdineshk/sg-finance-data-mcp` | 4 | community |  |
| `heavysword1/agentmarket` | 3 | community |  |
| `toolstem/toolstem-mcp-server` | 3 | community | Agent-ready financial intelligence MCP server. Three curated |
| `tickdb/tickdb-market-data-mcp` | 2 | community | TickDB-MCP is a Python MCP server implementation that connec |
| `financial-data/financial-data` | 2 | community | A comprehensive MCP server delivering real-time and historic |
| `vishalmdi/indian-stocks-mcp` | 2 | community | Ask Claude about Indian stocks. Minute-by-minute. No setup.
 |
| `deepsearch/korean-stocks` | 1 | community | Real-time Korean stock market intelligence for AI agents. Ac |
| `mcp-dir/mercado-mcp` | 1 | community | # Mercado Financeiro BR

Dados do mercado financeiro brasile |
| `tiger` | 0 | community | Trade stocks, options, and futures across US, HK, CN, and SG |
| `ak123aryan/nse-market-mcp` | 0 | community | Dalal Street MCP server connects to Indian stock market data |
| `evozim-hv/helium-financial` | 0 | community | Helium Financial is a premium micro-service from the M2MCent |
| `longbridge-official/longbridge-mcp` | 0 | community | US/HK markets — 133 tools: quotes, options, orders, fundamen |
| `marketflux/marketflux-mcp` | 0 | community | Connect Claude to a 33 million article financial news databa |
| `service-c09f/riskmodels` | 0 | official | **Clean US equity total returns + institutional risk decompo |
| `danelfin/ai-scores` | 0 | community | **Danelfin MCP server.** Bring AI Scores for US stocks, US E |
| `dehyinbox/dehy` | 0 | community | Real time SEC and market intelligence, structured at the sou |
| `jer-bouma/financetoolkit` | 0 | community | The Finance Toolkit gives AI assistants access to **200+ fin |
| `coinvest/coinvest` | 0 | community | Co-Invest lets you trade directly from ChatGPT, Claude, or y |
| `drillr/drillr` | 0 | community | Drillr is the official financial MCP for AI agents. One host |
| `nyuvlab/vlab` | 0 | community | Financial-risk data from NYU Stern's Volatility and Risk Ins |
| `get-cotrader/cotrader-mcp` | 0 | community | Analyze the stock market using natural language screening an |
| `sentisense/market-intelligence` | 0 | community | Bring SentiSense market intelligence into Claude and ChatGPT |
| `jamie-vw4h/aletaindex` | 0 | community | Financial narrative intelligence for AI agents — real-time n |
| `milesnee-e/data-rail` | 0 | community | Agent-safe crypto financial data access layer. Provides vali |
| `axiora/japan-financials` | 0 | community | 33 tools for Japanese financial data. Financials, ownership  |
| `flatlandfi/flatland` | 0 | official | Financial reasoning infrastructure for AI agents - typed mod |
| `fenglucc/ko-financial-data` | 0 | community | Real SEC, 13F, insider, congress & macro data your AI agent  |
| `paperandbeyond23/edgrapi` | 0 | community | Clean SEC EDGAR company financials for AI agents. Normalizes |

**能力 `calculator` — 18 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `EthanHenrickson/math-mcp` | 113093 | community | Enable your LLMs to perform accurate numerical calculations  |
| `AITutor3/calculator-mcp-test` | 3462 | community | Perform quick, reliable arithmetic including addition, subtr |
| `QuantOracle/quantoracle` | 167 | community | 63 deterministic quant computation tools for AI agents. Blac |
| `NutriBalance/nutribalance-mcp` | 20 | community |   Free nutrition tools for AI assistants — calculate TDEE &
 |
| `tradingcalc/tradingcalc-mcp` | 18 | community | 19 deterministic crypto futures calculators and workflows ac |
| `info-07of/property-finance-mcp` | 6 | community | Four UK property finance calculators for AI assistants: brid |
| `flopsindex/flopsindex` | 5 | community | FLOPS Compute Intelligence publishes settlement-grade GPU +  |
| `info-07of/property-mortgage-mcp` | 5 | community | UK mortgage calculators from [Fox Davidson](https://www.foxd |
| `rodriguezb-martin/hacecuentas` | 4 | community | Run 2,300+ practical calculators (finance, taxes ARCA/SAT, h |
| `Arithym/Arithym` | 2 | community | Exact arithmetic engine for AI agents. 62 tools across 22 do |
| `pb-vladislav/arcflow-destiny-matrix` | 2 | community | ArcFlow exposes the Destiny Matrix numerology calculator as  |
| `euclid/tools` | 0 | community | AI models do not calculate. They predict the most probable n |
| `naruto0414/osk-calculators` | 0 | community | Precision calculators for AI agents (medical, finance, engin |
| `open-ephemeris/openephemeris` | 0 | community | The most complete astronomical computation engine available  |
| `vedintel/astro-api` | 0 | community | Live Vedic astrology computations for AI agents — Swiss Ephe |
| `OjasKord/quantum-suitability-validator-mcp-server` | 0 | community | AI triage for quantum computing POC proposals. Screens befor |
| `quantumskils/african-fintech-mcp` | 0 | community | African fintech toolkit: mobile money fee calculator (M-Pesa |
| `jjbot1/Computer-mcp` | 0 | community |  |

### browser_automation  （需 1 种能力,各择一）

**能力 `browser_automation` — 30 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `zlurp/zlurp` | 4487 | community | Web scraping for AI agents. Convert any URL to clean markdow |
| `brightdata` | 939 | official | One (free) MCP for the Web. Easily search, crawl, navigate,  |
| `apify` | 465 | official | Web scraping and automation platform. Run scrapers, extract  |
| `browserbase` | 286 | official | Provides cloud browser automation capabilities using Stageha |
| `ScrapeGraphAI/scrapegraph-mcp` | 123 | official | Enable language models to perform advanced AI-powered web sc |
| `browser_tool` | 80 | official | Composio enables AI Agents and LLMs to authenticate and inte |
| `browserless/browserless-mcp` | 63 | community | Scrape any webpage to extract content in formats like Markdo |
| `DevEnterpriseSoftware/scrapi-mcp` | 50 | community | Web scraping using ScrAPI. Extract website content that is d |
| `kernel` | 21 | official | Deploy and manage Kernel apps, automate browsers, and search |
| `snaprender/snaprender` | 19 | community | Capture high-quality screenshots and PDFs of any website wit |
| `axel-belfort/screenshot-pdf` | 14 | community | Web capture API for AI agents. Take full-page screenshots (P |
| `noncelogic/rove` | 11 | community | Hosted Playwright browser automation for AI agents. Returns  |
| `scrayle/web-scraper` | 6 | community | Scrayle.com gives AI agents full web access through 35 tools |
| `hshintelligence/agentscrape` | 6 | community | **Pay-per-call web scraping for AI agents — no signup, no AP |
| `mailerlite` | 3 | official | Email marketing and automation platform. Create campaigns, m |
| `opengraph/opengraph` | 2 | community | Extract OpenGraph metadata, scrape website content, and take |
| `protostatis-dev/unbrowser` | 1 | community | Lightweight MCP browser for LLM agents. One native binary, n |
| `cloudflare/browser-rendering` | 1 | official | Browser rendering service. Fetch web pages, convert to markd |
| `zenrows/zenrows-mcp` | 1 | community | Scrape any webpage and return clean, LLM-ready content using |
| `pshivapr/selenium-mcp` | 0 | community | Enable AI assistants and applications to perform automated w |
| `relievedattention992-smithery/screenshotsmcp` | 0 | community |  |
| `xidik12/oculo` | 0 | community | Automate complex web browsing tasks like navigation, form fi |
| `glazyr/glazyr-viz` | 0 | community | Glazyr Viz bypasses fragile DOM scraping and Cloudflare bloc |
| `asteroid/asteroid` | 0 | community |   **Asteroid** lets you build, run, and manage AI **browser  |
| `foura/mcp` | 0 | community | Web scraping for AI agents. One smart tool fetches any publi |
| `krishpavulur/remote-device-server` | 0 | community | Drive real Android & iOS devices and web browsers from natur |
| `methia-farid2001/screenshotrender` | 0 | community | Take screenshots of any public website from Claude, Cursor,  |
| `contentful` | 0 | official | Contentful is a headless CMS allowing developers to create,  |
| `geromesportelli/snapforge` | 0 | community | Screenshots, PDFs & Markdown for AI agents |
| `scrapegraphai-inc/sgai` | 0 | community | The ScrapeGraphAI MCP Server is a production-ready Model Con |

### 3d_design  （需 1 种能力,各择一）
> 📝 无真 BlenderMCP;下列仅 3D 生成/渲染,非 Blender 脚本操作。建议本地起 Blender。

**能力 `blender_3d` — 21 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `promptibus/mcp` | 102 | community | Model intelligence for AI agents — syntax, parameters, prici |
| `sceneview/gateway` | 90 | community | Cross-platform 3D & AR for Android (Compose + Filament), iOS |
| `OjasKord/local-model-suitability-mcp` | 41 | official | AI model router. Checks whether to use local Ollama or cloud |
| `am-1m1k/muapi` | 20 | community | Access 400+ generative AI models directly from your AI assis |
| `snaprender/snaprender` | 19 | community | Capture high-quality screenshots and PDFs of any website wit |
| `caliper/caliper` | 16 | community | Caliper is an MCP server that accepts 3D geometry files and  |
| `Vivek-k3/modelsplus` | 12 | community | Discover and compare models and providers with up-to-date pr |
| `antoinebou12/uml` | 10 | community | UML-MCP Server is an MCP (Model Context Protocol) powered di |
| `beforeyouship/cost-model` | 3 | community | Model the realistic monthly cost of an LLM app **before you  |
| `cloudflare/browser-rendering` | 1 | official | Browser rendering service. Fetch web pages, convert to markd |
| `gaopengbin/cesium-mcp-runtime` | 1 | community | AI-powered 3D globe control via MCP — 59 tools for camera, l |
| `scrappycmo/share-of-model` | 1 | community | Track how often AI models mention and recommend your brand.  |
| `evozim-hv/3d-meshweaver` | 0 | community | 3D-MeshWeaver is a premium micro-service from the M2MCent fa |
| `evozim-hv/threejs-weaver` | 0 | community | ThreeJS Weaver is a premium micro-service from the M2MCent f |
| `francis-ros/rostro-mcp` | 0 | community | Turn any language model into a multimodal powerhouse that ca |
| `sudomock/sudomcp` | 0 | community | ## SudoMock MCP Server

Render photorealistic product mockup |
| `dragoneye/mcp-server` | 0 | community | Computer vision models with no training required. Create and |
| `service-c09f/riskmodels` | 0 | official | **Clean US equity total returns + institutional risk decompo |
| `NextCut/nextcut` | 0 | community | Automate video creation and editing workflows by rendering s |
| `glianalabs/gliana-ai` | 0 | community | Pay-per-call generative AI — 60+ models (image, video, music |
| `methia-farid2001/screenshotrender` | 0 | community | Take screenshots of any public website from Claude, Cursor,  |

## 二、tau3

### retail  （需 1 种能力,各择一）

**能力 `ecommerce_order` — 28 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `theagenttimes/ucp-gateway` | 15514 | official | AI Shopping tools for product search, comparison, and safe c |
| `hegetiby-jwao/woocommerce-mcp-hegetiby` | 654 | community | Give Claude full control of your WooCommerce store. Browse p |
| `huangmy157/ddd` | 603 | community | Search SFR’s catalog using natural language and refine resul |
| `regenique/elegance-commerce` | 106 | community | AI-powered commerce API for luxury skincare shopping. Enable |
| `hola-ps65/siil-ostomy-store` | 40 | community | Browse and purchase premium ostomy bag covers, support belts |
| `thibault/ecomgraph` | 14 | community | **Independent Shopify app discovery for AI agents.** Search, |
| `refund-decide/notary` | 9 | community | Determine refund eligibility for popular US consumer subscri |
| `bikefuchs/stub` | 7 | community | Bikefuchs is a bicycle parts price comparison and cart optim |
| `agenticshelf/agentic-shelf` | 5 | community | **Real-time product catalog, inventory, and pricing for AI a |
| `mdenius/titan-store` | 5 | community | TitanStore provides AI agents with programmatic access to co |
| `ucpchecker/ucp-checker` | 1 | community | A universal commerce gateway for AI agents to interact with  |
| `mcp-dir/nuvemshop-mcp` | 1 | community | # Nuvemshop

Plataforma de e-commerce Nuvemshop (Tiendanube) |
| `mcp-dir/pagseguro-mcp` | 1 | community | # PagSeguro

Pagamentos PagSeguro / PagBank, pedidos (orders |
| `mcp-dir/olist-mcp` | 1 | community | # Olist Tiny ERP

ERP de e-commerce Olist Tiny (ex-Tiny ERP) |
| `michael-defon/merka2a` | 1 | community | B2B commerce for AI agents: search wholesale electronics, ne |
| `shopify` | 0 | official | Build and manage online stores. List products, process order |
| `dsersx/product-mcp` | 0 | community | 🚀 The Professional Dropshipping MCP Server for DSers Automat |
| `diego-zjqo/wake-commerce` | 0 | community |  |
| `customblinds/shop` | 0 | community | Browse, price, configure and order custom-made blinds for So |
| `vivaldoeuropes/vivaldo-product-discovery` | 0 | community | Public read-only MCP server for Vivaldo.shop, a European onl |
| `eveoy/mcp` | 0 | community | **Eveoy brings real customers into real stores** — you pay $ |
| `ask-ai/data-connector` | 0 | community | # Ask AI Data Connector

  Connect 18+ e-commerce and busine |
| `kamolc4/swagger-petstore-mcp` | 0 | community | MCP server for the Swagger Petstore API with 19 tools. Gener |
| `periskop-ai/shopping-discovery` | 0 | community | Product discovery for AI agents: ranked products and bundles |
| `doomscrollr/mcp` | 0 | community | Build owned-audience websites: pages, posts, products, subsc |
| `instacart` | 0 | official | Instacart Developer Platform APIs to create shoppable lists/ |
| `zoho_inventory` | 0 | official | Zoho Inventory helps businesses track stock, manage orders,  |
| `OjasKord/hs-code-classifier-mcp-server` | 0 | official | HS code classifier. Classifies products to official HS tarif |

### airline  （需 1 种能力,各择一）
> 📝 仅搜索/预订,缺闭世界'改我的预订'

**能力 `flight_travel` — 40 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `kiwi` | 4088 | official | Search flights, compare prices, and manage travel bookings.  |
| `punitarani/fli` | 3921 | community | Search for Flights on Google Flights.

You can search for th |
| `ingrobertfodor/CHEAP_FLIGHTS_MCP` | 327 | community | MCP server for searching cheap flights in real-time. Searche |
| `ferryhopper` | 166 | official | Ferry booking platform across Europe. Search routes, compare |
| `agonzalez/prueba-mcp-seeker` | 64 | community | Search hotels by city, state, country, or geolocation and ex |
| `Stayker/hotel-booking` | 55 | community | The first MCP server that completes real hotel reservations  |
| `InfoseekAI/google-flight-search` | 46 | community | Search flights with Google Flights.

Get the mcp server url  |
| `gordgus/ignav-flights` | 43 | community | Hosted MCP server providing live flight prices, booking link |
| `albert-dwqs/viatsy-mcp` | 41 | community | Search Asia travel tours, browse guides, request quotes, fin |
| `shokjak/travel-deals-mcp` | 39 | community | Travel Deals MCP is a Model Context Protocol server that let |
| `tripuck894/tripuck` | 37 | community | Tripuck — Flight Meta-Search & Meeting Point.. |
| `onetrip/pulse` | 34 | community | Access comprehensive travel and location data to streamline  |
| `google/hotels` | 32 | community | Search hotels and vacation rentals on Google Hotels. No API  |
| `hello-3ubk/booboooking` | 26 | community | booboooking is a booking app. As a provider you can set up y |
| `rowhint-ntm5/RowHint` | 25 | community | # RowHint MCP Server

Airline seat quality intelligence via  |
| `award-flight-daily/mcp-server` | 20 | community | Official Industry Standard MCP for Travel Awards, Points, an |
| `info-00wt/hemmabo-mcp-server` | 19 | official | HemmaBo MCP server for AI-ready direct booking on host-owned |
| `greg/Agentorist` | 16 | community | The booking layer for AI agents. Search, discover, and book  |
| `moodtrip/Adin-Flights-search` | 13 | community | AI-powered flight search and booking, by MoodTrip.Ai.

Adin  |
| `steve-gi45/pixie-vacations-mcp` | 12 | community | **Pixie Vacations** — the first U.S. travel agency MCP serve |
| `trip1/trip1` | 10 | community | [Trip1](https://trip1.com) lets you search and book hotels w |
| `easyweek/easyweek` | 8 | official | EasyWeek is an all-in-one booking and business management pl |
| `AITutor3/icn-mcp` | 6 | community | Get real-time departure hall congestion, flight statuses, an |
| `xltnapps/octotrip-rental-cars` | 4 | community | # OctoTrip Rental Cars MCP Server

Free, no-login MCP server |
| `moodtrip/moodtrip-hotel-search` | 4 | community | MoodTrip is an AI-powered hotel search that understands natu |
| `letsfg` | 2 | community | Agent-native flight search. 102 airline connectors fire in p |
| `heavysword1/agentflight` | 2 | community |  |
| `sunrays-dev/booking` | 2 | community | Book real local tradespeople — plumber, electrician, HVAC, a |
| `InfoseekAI/bookingdotcom` | 1 | community | Search flights on Booking.com

Get the mcp server url @ http |
| `takecarsdd/italy-transfers` | 1 | community | Real-time train, bus, ferry and private transfer prices betw |
| `tripadvisor/search` | 1 | community | Search Tripadvisor for hotels, restaurants, and attractions. |
| `xltnapps/octotrip-flights` | 0 | community | Free, no-login MCP server for searching and comparing flight |
| `InfoseekAI/flight-agent-matrix` | 0 | community | Search Google, Skyscanner, Skiplagged, Booking.com in real t |
| `agentgateway/agentgateway-marketplace` | 0 | community | AI commerce platform — WooCommerce store products, flights,  |
| `untap/claims` | 0 | community | **Untap** finds money UK travellers are already owed and sur |
| `airport-pickups-london/London-airport-transfers` | 0 | community | Provide instant quotes and bookings for private transfers be |
| `flightdb/flight-history` | 0 | community | ### FlightDB (`flightdb`)

- **URL:** https://flightdb.org
- |
| `ahmednegm-1711/maqami-travel` | 0 | community | Book hotels worldwide — search, price, prebook & book across |
| `plany/plany-mcp` | 0 | community | Organize travel itineraries by creating detailed trips with  |
| `floyd/mcp-server` | 0 | community | Booking infrastructure with the guarantees agents need: temp |

### telecom  （需 2 种能力,各择一）
> 📝 helpdesk+账单,缺运营商设备排障

**能力 `helpdesk_support` — 12 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `hubspot` | 470 | official | Access your HubSpot CRM through AI assistants. Search contac |
| `intercom` | 132 | official | Chat with customers via live messaging, manage support ticke |
| `favcrm/favcrm` | 68 | official | **Agentic CRM for service businesses** — 136 typed tools acr |
| `gorgias` | 1 | official | Gorgias is a helpdesk and live chat platform specializing in |
| `recursive/support` | 1 | community | Query the Recursive AI support agent platform — pricing, fea |
| `mcp-dir/ifood-mcp` | 1 | community | # iFood

Insights da sua loja no iFood direto no chat do seu |
| `support-9ef4/Wayforth` | 1 | official | The API runtime for AI agents.
One tool call. Any API. No se |
| `zendesk` | 0 | official | Manage support tickets, help center articles, and customer c |
| `plain` | 0 | community | AI-powered customer support platform. Manage threads, custom |
| `spark1security/n0s1-mcp` | 0 | community | Scan Jira, Confluence, Slack, GitHub, GitLab, Zendesk, Linea |
| `pierre/htt` | 0 | community | Create instant call links for Snapcall conversations. Start  |
| `cod-gb2l/StudioMeyer-CRM` | 0 | community | AI-native CRM as MCP Server. 33 tools for contacts, pipeline |

**能力 `billing_subscription` — 15 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `coal/coal-payments` | 42 | community | # Coal

Coal gives AI agents a real checkout.

Discover merc |
| `umg-gpt/moltpe` | 26 | community | AI-native payment infrastructure that gives AI agents isolat |
| `harvest` | 5 | official | Log billable hours, manage projects, and send invoices. Trac |
| `runpay/marketplace` | 5 | community | Stripe-native marketplace where AI agents autonomously disco |
| `aiamindennapokban/billingo-mcp` | 3 | community | Manage invoices, partners, and business expenses through the |
| `xqb/vibe-pay` | 2 | community | Platform access code. Email coryhigham@gmail.com with subjec |
| `promptfax/promptfax` | 1 | community | PromptFax is a pay-per-use remote MCP server that lets an AI |
| `stripe` | 0 | official |  |
| `zoho_invoice` | 0 | official | Zoho Invoice simplifies billing, recurring payments, and exp |
| `square` | 0 | official | Process payments, manage subscriptions, send invoices, and h |
| `paypal` | 0 | official | Create and share payment links, send invoices, and view rece |
| `sacha/swiss-qr-bill` | 0 | community | Generate and validate Swiss QR-Bills (Swiss Payment Standard |
| `support-ivr7/invoicexml` | 0 | community | InvoiceXML brings e-invoice compliance to your AI agent. Cre |
| `aiamindennapokban/nav-online-invoice-mcp` | 0 | community | Manage and query Hungarian invoice data directly through the |
| `segawa4321/agent-budget-guard` | 0 | community | Pre-payment budget check and post-payment invoice routing fo |

### banking  （需 1 种能力,各择一）
> 📝 多为真账户连接器,闭世界 banking 无原生对应

**能力 `banking_account` — 10 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `jonathan-7udh/inferventis-finance` | 24 | community | 19 production-ready financial tools for AI agents. Covers cu |
| `douglas/banco-mcp` | 1 | community | # Banco MCP — Open Finance Brasil

Conecte 30+ bancos brasil |
| `mcp-dir/wise-mcp` | 1 | community | # Wise

MCP da Wise (https://wise.com), acesso à conta multi |
| `aa-9xxm/ohmyfin` | 1 | community | Cross-border payment and banking intelligence for AI agents: |
| `mcp-dir/nubank-mcp` | 1 | community | # Nubank MCP

Conecte sua conta do **Nubank** ao Claude, Cha |
| `hiro` | 0 | official | Manage personal finances by aggregating bank accounts, inves |
| `banksync/banksync-mcp` | 0 | community | Connect AI agents to real bank accounts — transactions, bala |
| `aequitas-labs/matcha-money` | 0 | community | Develop your ritual for financial wellness.

Connect your ac |
| `mercury` | 0 | community | Online business banking services. Businesses can apply for a |
| `appfinkai/finkai` | 0 | community | FinkAI is a personal-finance MCP server for the authenticate |

### banking_knowledge  （需 1 种能力,各择一）
> 📝 通用 RAG,非银行专用库

**能力 `rag_knowledge` — 32 个可用替代(按 useCount)：**

| server | useCount | 类型 | 描述 |
|---|---|---|---|
| `jina` | 4243 | official | AI-powered search and retrieval platform. Search the web, re |
| `lanonasis/lanonasis-mcp` | 85 | community | Manage long-term memory across projects with fast semantic s |
| `infranodus/mcp-server-infranodus` | 48 | official | Map text into knowledge graphs to create a structured repres |
| `lanonasis/lano-enterprise-mcp` | 31 | community | Store and retrieve semantic memories using advanced vector s |
| `omegamemory/omega-memory` | 26 | community | Maintain persistent project context by storing decisions, le |
| `node2flow/gemini-file-search-rag` | 24 | community | MCP server for Google's Gemini File Search and RAG (Retrieva |
| `mem0ai/mem0-memory-mcp` | 21 | official | Save, search, and manage long-term memories across users and |
| `docfork/docfork` | 14 | official | Search and retrieve documentation from GitHub repositories a |
| `purmemo/purmemo-mcp` | 14 | community | AI conversation memory that works everywhere. Save and recal |
| `velarynai/ragora` | 3 | community | Search across all your knowledge bases to retrieve relevant  |
| `supermemory` | 1 | official | Supermemory's universal Memory MCP will save and bring your  |
| `dejaview` | 1 | community | Store and retrieve facts about entities through a persistent |
| `kulkarnianirudha8/byteaskai` | 1 | community | # ByteAsk Embedded Docs MCP

Page-cited retrieval over embed |
| `cloudflare/ai-search` | 0 | official | AI Search (AutoRAG) management. List and search documents ac |
| `knowledge-raven/RAV3N` | 0 | community | Make your knowledge agent-ready. Connect docs from Confluenc |
| `pquattro-3b11/memoraeu` | 0 | community | Personal memory layer for AI assistants. Store, search and r |
| `evozim-hv/repo-to-rag` | 0 | community | Repo-to-RAG is a premium micro-service from the M2MCent fact |
| `team-sw2r/myaitwin` | 0 | community | A personal RAG database you build from chat. Store your know |
| `remembra-ai/remembra` | 0 | community | Persistent memory for AI agents. Store context, recall seman |
| `pulsomex/agentmemo` | 0 | community | Give your AI agents a shared memory pool.

When Agent A lear |
| `support-0vd1/llmtomd` | 0 | community | **LLMtoMD is the memory layer for AI coding agents.** It con |
| `captureai/capturemcp` | 0 | community | capture is a memory layer that ingests emails, Slack threads |
| `agentbay/memory` | 0 | community |                                                 
Persistent  |
| `plurality-network/ai-context-flow` | 0 | community | Universal memory for AI agents and tools. Save, organize and |
| `ai-jcce/mcp-contexta` | 0 | community | Contexta gives AI assistants a persistent, typed memory laye |
| `james-esah/ultramemory` | 0 | community | Cross-tool memory for your AI that recalls first every turn  |
| `hifriendbot/cogmemai` | 0 | community | Persistent cloud memory for Ai coding assistants. 33 MCP too |
| `cherkavskyi/memplato` | 0 | community | Personal MCP memory server that runs on your Android phone v |
| `xmemo/xmemo` | 0 | community | XMemo is the cloud memory layer for AI agents: a hosted, use |
| `eve/eve-mcp` | 0 | community | One Memory. Every Agent.
Eve gives teams one managed memory  |
| `mifactory-bot/agent-memory` | 0 | community | Store and retrieve persistent information across different s |
| `OjasKord/document-integrity-validator-mcp` | 0 | official | AI reasoning checks any document against named international |
