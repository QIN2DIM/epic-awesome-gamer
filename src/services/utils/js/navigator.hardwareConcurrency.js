// https://github.com/berstend/puppeteer-extra/commit/0a26ae5f95e625ade32dfb0583dd57e994b821a1#diff-37d207e17f30e9cd42c82eeda587c5dda38dd528ec77db8c65494013fb8b2769

utils.replaceGetterWithProxy(
    Object.getPrototypeOf(navigator),
    'hardwareConcurrency',
    utils.makeHandler().getterValue(opts.hardwareConcurrency)
)