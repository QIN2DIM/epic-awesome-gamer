// replace Headless references in default useragent
const current_ua = navigator.userAgent
Object.defineProperty(Object.getPrototypeOf(navigator), 'userAgent', {
    get: () => opts.navigator_user_agent || current_ua.replace('HeadlessChrome/', 'Chrome/')
})

// https://github.com/ultrafunkamsterdam/undetected-chromedriver/blob/7cb068d977a062a1e82c8dd676918089df74bbca/undetected_chromedriver/__init__.py#L497
// Object.defineProperty(navigator, 'maxTouchPoints', {
//     get: () => 1
// })