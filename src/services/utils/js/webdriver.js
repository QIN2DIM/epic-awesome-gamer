// set webdriver to `false` instead of `undefined`
// https://github.com/ultrafunkamsterdam/undetected-chromedriver/blob/7cb068d977a062a1e82c8dd676918089df74bbca/undetected_chromedriver/__init__.py#L467
Object.defineProperty(window, 'navigator', {
    value: new Proxy(navigator, {
        has: (target, key) => (key === 'webdriver' ? false : key in target),
        get: (target, key) =>
            key === 'webdriver' ?
                false :
                typeof target[key] === 'function' ?
                    target[key].bind(target) :
                    target[key]
    })
});
