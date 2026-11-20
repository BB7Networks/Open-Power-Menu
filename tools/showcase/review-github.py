#!/usr/bin/env python3
"""Review the actual public GitHub-rendered README in four browser contexts.

Requires Playwright and Chromium. TLS verification stays enabled. A managed
proxy's CA can be trusted in an isolated browser HOME via --browser-home.
Evidence stays outside the repository; this is not a local Markdown mockup.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
from playwright.sync_api import sync_playwright


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',default='https://github.com/BB7Networks/Open-Power-Menu/blob/docs/2.1.0-readme-showcase/README.md')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--browser-home',type=Path)
    p.add_argument('--chromium',default=shutil.which('chromium'))
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    env=dict(os.environ)
    if args.browser_home:env['HOME']=str(args.browser_home.resolve())
    reports=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'],env=env)
        for width,height,label in ((1440,1000,'desktop'),(390,844,'mobile')):
            for scheme in ('light','dark'):
                name=label+'-'+scheme
                context=browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1,color_scheme=scheme)
                page=context.new_page();response=page.goto(args.url,wait_until='domcontentloaded',timeout=60000)
                assert response and response.status==200,(name,response.status if response else None)
                article=page.locator('article.markdown-body').first
                article.wait_for(timeout=30000)
                page.wait_for_function("document.querySelectorAll('article.markdown-body img').length >= 39",timeout=30000)
                # Visit each real image to load GitHub's lazy resources.
                for picture in article.locator('img').all():
                    picture.scroll_into_view_if_needed();picture.evaluate('(image) => image.decode()')
                metrics=page.evaluate('''() => {
                    const article=document.querySelector('article.markdown-body');
                    return {title:document.title,url:location.href,
                      viewport:[innerWidth,innerHeight],documentWidth:document.documentElement.scrollWidth,
                      colorMode:document.documentElement.dataset.colorMode,
                      prefersDark:matchMedia('(prefers-color-scheme: dark)').matches,
                      bodyBackground:getComputedStyle(document.body).backgroundColor,
                      articleBackground:getComputedStyle(article).backgroundColor,
                      images:[...article.querySelectorAll('img')].map(image=>({
                        src:image.currentSrc,alt:image.alt,width:image.naturalWidth,height:image.naturalHeight,
                        renderedWidth:image.getBoundingClientRect().width,
                        linked:!!image.closest('a[href]'),complete:image.complete})),
                      tables:[...article.querySelectorAll('table')].map(table=>({
                        width:table.getBoundingClientRect().width,scrollWidth:table.scrollWidth,
                        overflow:getComputedStyle(table).overflowX}))};
                }''')
                assert metrics['documentWidth']<=width,(name,'page overflow',metrics['documentWidth'])
                assert all(i['width'] and i['height'] and i['complete'] and i['alt'] and i['linked'] for i in metrics['images'])
                assert metrics['prefersDark']==(scheme=='dark')
                for section,heading in [('opening','Open Power Menu'),('defaults','Out of the box, and make it yours'),
                    ('appearance','Your menu, your style'),('editing','Make it yours')]:
                    target=article.get_by_role('heading',name=heading,exact=True)
                    target.scroll_into_view_if_needed()
                    page.screenshot(path=str(args.output/(name+'-'+section+'.png')))
                metrics['view']=name;reports.append(metrics)
                print(name,'PASS',len(metrics['images']),'loaded linked images',flush=True)
                context.close()
        browser.close()
    (args.output/'github-review.json').write_text(json.dumps(reports,indent=2)+'\n')


if __name__=='__main__':main()
