#include "physical_keys.hpp"
#include <QtTest>
using namespace Opm;

static KeyAdmission deliver(PhysicalPresses &keys, int key, quint32 scan, quint32 timestamp, bool qtRepeat) {
    QKeyEvent event(QEvent::KeyPress, key, Qt::NoModifier, scan, 0, 0, {}, qtRepeat);
    event.setTimestamp(timestamp);
    return keys.take(event.nativeScanCode(), quint32(event.timestamp()), key == Qt::Key_Up || key == Qt::Key_Down);
}
class PhysicalKeysTests : public QObject {
    Q_OBJECT
  private slots:
    void heldKeys_data() {
        QTest::addColumn<int>("key"); QTest::addColumn<bool>("repeat");
        for (int key : {Qt::Key_U,Qt::Key_R,Qt::Key_I,Qt::Key_S,Qt::Key_H,Qt::Key_L,
                        Qt::Key_Return,Qt::Key_Escape,Qt::Key_Left,Qt::Key_Right})
            for (bool repeat : {false,true})
                QTest::newRow(qPrintable(QString("%1-qtRepeat%2").arg(key).arg(repeat))) << key << repeat;
    }
    void heldKeys() {
        QFETCH(int,key); QFETCH(bool,repeat);
        PhysicalPresses keys; keys.collect(true);
        keys.press(30,100,5,false);
        QCOMPARE(deliver(keys,key,30,100,repeat),KeyAdmission::Press);
        // Core X11 synthetic releases do not enter this raw ledger. Neither
        // losing focus nor a bogus Qt "fresh press" grants a second selection.
        for (quint32 time=101;time<200;++time) {
            QCOMPARE(deliver(keys,key,30,time,repeat),KeyAdmission::Reject);
            keys.press(30,time,5,false); // Also reject duplicate raw downs.
            QCOMPARE(deliver(keys,key,30,time,repeat),KeyAdmission::Reject);
        }
        keys.release(30,5); keys.press(30,200,5,false);
        QCOMPARE(deliver(keys,key,30,200,repeat),KeyAdmission::Press);
        QCOMPARE(deliver(keys,key,30,200,repeat),KeyAdmission::Reject);
    }
    void rapidBatchAndEqualTimestamps() {
        for (bool repeat : {false,true}) {
            PhysicalPresses keys;keys.collect(true);
            // Both physical presses may arrive before Qt delivers the first.
            keys.press(30,1234,5,false);keys.release(30,5);keys.press(30,1234,5,false);keys.release(30,5);
            QCOMPARE(deliver(keys,Qt::Key_U,30,1234,repeat),KeyAdmission::Press);
            QCOMPARE(deliver(keys,Qt::Key_U,30,1234,repeat),KeyAdmission::Press);
            QCOMPARE(deliver(keys,Qt::Key_U,30,1234,repeat),KeyAdmission::Reject);
        }
    }
    void closeReopenUnknownAndWrongEvidence() {
        PhysicalPresses keys;keys.collect(true);keys.press(30,1,5,false);
        QCOMPARE(deliver(keys,Qt::Key_U,30,1,false),KeyAdmission::Press);
        keys.collect(false);keys.collect(true);
        QCOMPARE(deliver(keys,Qt::Key_U,30,1,false),KeyAdmission::Reject);
        keys.press(30,2,5,false);QCOMPARE(deliver(keys,Qt::Key_U,30,2,false),KeyAdmission::Reject);
        keys.release(30,5);keys.press(30,3,5,false);
        QCOMPARE(deliver(keys,Qt::Key_U,31,3,false),KeyAdmission::Reject);
        QCOMPARE(deliver(keys,Qt::Key_U,30,4,false),KeyAdmission::Reject);
        QCOMPARE(deliver(keys,Qt::Key_U,30,3,true),KeyAdmission::Press);
        keys.snapshot({30});keys.press(30,4,5,false);
        QCOMPARE(deliver(keys,Qt::Key_U,30,4,false),KeyAdmission::Reject);
        keys.release(30,5);keys.press(30,5,5,false);
        QCOMPARE(deliver(keys,Qt::Key_U,30,5,false),KeyAdmission::Press);
        keys.snapshot({}); // Hierarchy/session uncertainty invalidates proofs.
        QCOMPARE(deliver(keys,Qt::Key_U,30,5,false),KeyAdmission::Reject);
    }
    void nativeRepeatAndNavigation() {
        PhysicalPresses keys;keys.collect(true);
        keys.press(30,1,5,true);QCOMPARE(deliver(keys,Qt::Key_U,30,1,false),KeyAdmission::Reject);
        keys.release(30,5);keys.press(111,2,5,false);
        QCOMPARE(deliver(keys,Qt::Key_Up,111,2,false),KeyAdmission::Press);
        QCOMPARE(deliver(keys,Qt::Key_Up,111,3,false),KeyAdmission::NavigationRepeat);
        keys.release(111,5);
        QCOMPARE(deliver(keys,Qt::Key_Up,111,4,false),KeyAdmission::Reject);
    }
    void boundedQueueFailsClosed() {
        PhysicalPresses keys;keys.collect(true);
        for (int n=1;n<=513;++n) {keys.press(30,n,5,false);keys.release(30,5);}
        QCOMPARE(deliver(keys,Qt::Key_U,30,1,false),KeyAdmission::Reject);
        QCOMPARE(deliver(keys,Qt::Key_U,30,513,false),KeyAdmission::Press);
    }
    void waylandSharedHoldAndUnknownRelease() {
        PhysicalKeys keys;QVERIFY(!keys.isX11());keys.setActive(true);
        QKeyEvent press(QEvent::KeyPress,Qt::Key_U,Qt::NoModifier,"u",false);
        QKeyEvent repeat(QEvent::KeyPress,Qt::Key_U,Qt::NoModifier,"u",true);
        QKeyEvent repeatedRelease(QEvent::KeyRelease,Qt::Key_U,Qt::NoModifier,"u",true);
        QKeyEvent release(QEvent::KeyRelease,Qt::Key_U,Qt::NoModifier,"u",false);
        QCOMPARE(keys.press(press),KeyAdmission::Press);
        keys.release(repeatedRelease);
        QCOMPARE(keys.press(press),KeyAdmission::Reject); // False Qt repeat flag in the other window.
        QCOMPARE(keys.press(repeat),KeyAdmission::Reject);
        keys.setActive(false);keys.setActive(true);
        QCOMPARE(keys.press(press),KeyAdmission::Reject);
        keys.release(release); // Release can be delivered by any window in the tree.
        QCOMPARE(keys.press(press),KeyAdmission::Press);
        keys.release(release);keys.setActive(false);
        QCOMPARE(keys.press(press),KeyAdmission::Reject);
        keys.setActive(true);QCOMPARE(keys.press(press),KeyAdmission::Reject);
    }
};
QTEST_MAIN(PhysicalKeysTests)
#include "physical_keys_test.moc"
