#!/usr/bin/env python3
"""Read-only observation of real X11 dismissals on plasma_popup.py's private seat.

The screenshot helper creates no windows and starts before any reproduction.
Native xev observers never request focus. Timeouts are test observation bounds,
not production dismissal delays. No fixture action executes a command.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from plasma_startup import wait_for


def capture_server(directory):
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication([])
    directory = Path(directory)
    for label in sys.stdin:
        app.processEvents()
        path = directory/(label.strip()+'.png')
        assert app.primaryScreen().grabWindow(0).save(str(path))
        print('captured', flush=True)


def exercise(args, case, spawn, command, move, state, log, shell, app_id):
    from PySide6.QtGui import QImage
    from plasma_popup import traces
    pixels = case/'pixels'; pixels.mkdir()
    capture = subprocess.Popen([sys.executable, __file__, '--capture', str(pixels)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    def screenshot(label):
        capture.stdin.write(label+'\n'); capture.stdin.flush()
        assert capture.stdout.readline().strip() == 'captured'
    def native(wid):
        r = subprocess.run(['xwininfo', '-id', wid], capture_output=True, text=True)
        if r.returncode: return {'id':wid, 'map':'destroyed'}
        status = re.search(r'Map State: (\S+)', r.stdout)
        return {'id':wid, 'map':status[1] if status else 'unknown', 'info':r.stdout}
    def windows():
        result = {}
        for wid in command('xdotool','search','--pid',str(shell.pid)).splitlines():
            r = subprocess.run(['xprop','-id',wid,'_NET_WM_WINDOW_TYPE','WM_TRANSIENT_FOR','_KDE_SLIDE'],capture_output=True,text=True)
            if r.returncode==0: result[wid]=r.stdout
        return result
    records = []
    observed = set()
    try:
        spawn([sys.executable,str(Path(__file__).resolve().parents[2]/'tools/trace-x11-popup.py'),
               '--pid',str(shell.pid),'--seconds','120'],'native-window-trace.jsonl')
        # Genuine native shortcut in this isolated profile, not a QML method call.
        command('qdbus6','org.kde.plasmashell','/PlasmaShell','org.kde.PlasmaShell.evaluateScript',
                'panels().forEach(p=>p.widgets().forEach(w=>{if(w.type==="org.openpowermenu.start") w.globalShortcut="Meta+X";}));')
        for effect in ('slidingpopups','blur','contrast'):
            command('qdbus6','org.kde.KWin','/Effects','org.kde.kwin.Effects.loadEffect',effect)
        support = command('qdbus6','org.kde.KWin','/KWin','org.kde.KWin.supportInformation')
        (case/'compositor.txt').write_text(support)
        assert 'Compositing is active' in support, support
        for flyout in (False, True):
            for dismiss in ('escape','outside','meta_x'):
                label = ('flyout' if flyout else 'root')+'-'+dismiss
                command('xdotool','windowactivate','--sync',app_id)
                button = state()['button']; move([button['x'],button['y']])
                screenshot(label+'-before')
                command('xdotool','click','3')
                wait_for(lambda: state()['expanded'] and len(state()['popup'].get('rows',[]))==7)
                rows = state()['popup']['rows']
                if flyout:
                    move(rows[5]['point'])
                    wait_for(lambda: state()['popup']['flyout']['window']['visible'])
                    rect=state()['popup']['flyout']['window']['geometry']
                    move([rect[0]+rect[2]/2,rect[1]+rect[3]/3])
                else:
                    move(rows[-1]['point'])
                screenshot(label+'-open')
                relevant = {wid:props for wid,props in windows().items()
                            if 'APPLET_POPUP' in props or '_NET_WM_WINDOW_TYPE_UTILITY' in props}
                mapped = [wid for wid in relevant if native(wid)['map']=='IsViewable']
                assert len(mapped) >= (2 if flyout else 1), relevant
                for wid in mapped:
                    if wid not in observed:
                        spawn(['stdbuf','-oL','xev','-id',wid,'-event','structure','-event','expose'],f'xevents-{wid}.log')
                        observed.add(wid)
                before = state()
                if dismiss=='escape':
                    # Mouse-opened flyouts do not take keyboard focus.
                    command('xdotool','key','Escape')
                elif dismiss=='outside':
                    move([1000,100]); command('xdotool','click','1')
                else:
                    command('xdotool','key','super+x')
                start = time.monotonic()
                for checkpoint in (0.05,0.25,0.8,1.6):
                    time.sleep(max(0,checkpoint-(time.monotonic()-start)))
                    data={'case':label,'after_ms':round((time.monotonic()-start)*1000),
                          'time_ms':time.time()*1000,'state':state(),
                          'windows':[native(wid) for wid in mapped]}
                    records.append(data)
                    screenshot(label+'-closed-'+str(checkpoint))
                after = state()
                assert not after['expanded'], (label,after)
                if not args.diagnostics_off:
                    changed=[r for r in traces(log) if r['callback']=='root.expandedChanged'][-1]
                    assert changed['details']['origin']==('external-to-opm' if dismiss=='outside' else 'opm'), changed
                assert not after['popup']['window']['visible'], (label,after)
                assert not after['popup']['flyout']['window']['visible'], (label,after)
                assert not after['popup']['inPanelWindow'], (label,after)
                assert all(native(wid)['map'] in ('IsUnMapped','IsUnmapped','destroyed') for wid in mapped), records[-1]
                # Check whether a later panel hover changes stale content. This
                # happens only AFTER the stationary-pointer observation interval.
                move([button['x'],button['y']]); screenshot(label+'-after-panel-hover')
                # Ignore the launcher/button hover indicator at the panel's
                # left edge. Compare the panel beneath the popup's text area.
                panel=before['panelWindow']['geometry']; rect=before['popup']['window']['geometry']
                x=round((rect[0]+100)*args.scale); y=round(panel[1]*args.scale)
                width=round((rect[2]-110)*args.scale); height=round(panel[3]*args.scale)
                reference=QImage(str(pixels/(label+'-after-panel-hover.png'))).copy(x,y,width,height)
                for moment in ('0.8','1.6'):
                    closed=QImage(str(pixels/(label+'-closed-'+moment+'.png'))).copy(x,y,width,height)
                    assert not closed.isNull() and not reference.isNull()
                    # Panel blur/contrast can change its tint after activation;
                    # retain measurements, not a misleading universal pixel-pass.
                    differences=[]
                    for py in range(height):
                        for px in range(width):
                            a=closed.pixelColor(px,py).getRgb()[:3]
                            b=reference.pixelColor(px,py).getRgb()[:3]
                            differences.append(max(abs(a[i]-b[i]) for i in range(3)))
                    records.append({'case':label,'panel_comparison':moment,
                        'max_channel_delta':max(differences),'mean_max_channel_delta':sum(differences)/len(differences),
                        'changed_pixels':sum(d>0 for d in differences),'pixels':len(differences)})
                print('PASS dismissal' ,label,'hidden',args.hidden,flush=True)
        if args.diagnostics_off:
            assert all(r['callback']=='fixture-sample' for r in traces(log))
        assert set((case/'backend.log').read_text().splitlines()) <= {'GetMenu','GetIntegration','PowerCapabilitiesPending'}
    finally:
        (case/'dismissal-states.json').write_text(json.dumps(records,indent=2))
        capture.stdin.close(); capture.wait(timeout=5)


if __name__=='__main__':
    if len(sys.argv)==3 and sys.argv[1]=='--capture': capture_server(sys.argv[2])
    else: raise SystemExit('Use plasma_popup.py --dismissal --output NEW_DIRECTORY')
