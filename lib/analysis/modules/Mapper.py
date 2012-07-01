"""
Description:
    
Input: event / site data previously analyzed by photostim
Output: 
    - per-event probability of being direct / evoked / spont
    - per-site probability of having evoked / direct input
    - per-cell measurements of direct and presynaptic area

Whereas photostim largely operates on a single stimulation (or a single stimulation site)
at a time, mapper operates on complete mapping datasets--multiple scans within a cell

Ideally, this module should replace the 'stats' and 'map' functionality in photostim
as well as integrate megan's map analysis, but I would really like it 
to be an independent module (and if it's not too difficult, it should _also_ be possible
to integrate it with photostim)


Features:

    - tracks spontaneous event rate over the timecourse of a cell as well as the prevalence
    of specific event features -- amplitude, shape, etc. This data is used to 
    determine:
        - For each event, the probability that it is evoked / spontaneous / direct
            - If we can get a good measure of this, we should also be able to formulate
              a distribution describing spontaneous events. We can then ask how much of the 
              actual distribution exceeds this and automatically partition events into evoked / spont.
        - For each site, the probability that it contains evoked and/or direct events
    This should have no notion of 'episodes' -- events at the beginning of one trace
    may have been evoked by the previous stim.
    - can report total number of evoked presynaptic sites per atlas region, total area of direct activation
    
    - display colored maps in 3d atlas
    
    - event-explorer functionality:    (perhaps this should stay separate)
        - display scatter plots of events based on various filtering criteria
        - mark regions of events within scatter plot as being invalid
        - filter generator: filter down events one criteria at a time, use lines / rois to control limits
            eg: plot by amplitude, tau; select a population of events that are known to be too large / fast
                replot by relative error and length/tau ratio; select another subset
                once a group is selected / deselected, tag the set (new column in events table)
                


Changes to event detector:
    - Ability to manually adjust PSP fits, particularly for direct responses (this goes into event detector?)
    - Ability to decrease sensitivity after detecting a direct event
    - Move region selection out of event detector entirely; should be part of mapper
    (the mapper can add columns to the event table if we want..)
    

    
Notes on probability computation:

    We need to be able to detect several different situations:
    
    (1) Obvious, immediate rate change
    
    |___||____|_|_______|____|___|___|_|||||||_|_||__|_||___|____|__|_|___|____|___
                                      ^
    (2) Obvious, delayed rate change
    
    |___||____|_|_______|____|___|___|_|____|__|_|___|___|_||_|_||_|_|__|_|_||_____
                                      ^
    (3) Non-obvious rate change, but responses have good precision   
    
    |______|______|_________|_______|____|______|________|________|_________|______
    _____|___________|_______|___|_______|__________|____|______|______|___________
    ___|________|_________|___|______|___|__|_________|____|_______|___________|___
                                      ^
    (4) Very low spont rate (cannot measure intervals between events)
        with good response precision
        
    ______________________________________|________________________________________
    ________|___________________________________|__________________________________
    _________________________________________|________________________|____________
                                      ^
    (5) Non-obvious rate change, but response amplitudes are very different
    
    __,______.___,_______.___,_______,_____|___,_____._________,_,______.______,___
                                      ^

    

"""












## Code for playing with poisson distributions

import numpy as np
import scipy.stats as stats
import scipy.misc
import pyqtgraph as pg
import pyqtgraph.console
import user
import pyqtgraph.multiprocess as mp

def poissonProcess(rate, tmax=None, n=None):
    """Simulate a poisson process; return a list of event times"""
    events = []
    t = 0
    while True:
        t += np.random.exponential(1./rate)
        if tmax is not None and t > tmax:
            break
        events.append(t)
        if n is not None and len(events) >= n:
            break
    return np.array(events)

def poissonProb(events, xvals, rate, correctForSelection=False):
    ## Given a list of event times,
    ## evaluate poisson cdf of events for multiple windows (0 to x for x in xvals)
    ## for each value x in xvals, returns the probability that events from 0 to x
    ## would be produced by a poisson process with the given rate.
    #n = (events[:, np.newaxis] < xvals[np.newaxis,:]).sum(axis=0)
    #p = stats.poisson(rate * x)
    
    ## In the case that events == xvals (the windows to evaluate are _selected_ 
    ## based on the event times), we must apply a correction factor to the expectation
    ## value: rate*x  =>  rate * (x + 1/rate). This effectively increases the size of the window
    ## by one period, which reduces the probability to the expected value.
    
    ## return 1.0 - p.cdf(n)
    
    y = []
    for i in range(len(xvals)):
        x = xvals[i]
        e = 0
        if correctForSelection:
            e = 1./rate
        y.append(stats.poisson(rate * (x+e)).cdf(i+1))
    return 1.0-np.array(y)

def poissonScore(events, rate):
    ## 1) For each event, measure the probability that the event and those preceding
    ##    it could be produced by a poisson process
    ## 2) Of the probabilities computed in 1), select the minimum value
    ## 3) X = 1 / min to convert from probability to improbability
    ## 4) apply some magic: Y = sqrt(X) / 2  -- don't know why this works, but
    ##    it scales the value such that 1 in Y random trials will produce a score >= Y
    
    pp = poissonProb(events, events, rate, correctForSelection=True)
    if len(pp) == 0:
        return 1.0
    else:
        return ((1.0 / pp.min())**1.0) / (rate ** 0.5)

        
#def poissonIntegral(events, rate, tMin, tMax):
    ## This version sucks
    #pp = poissonProb(events, events, rate)
    #if len(pp) == 0:
        #return 1.0
    #else:
        #return (1.0 / pp.mean())**0.5
        
poissonIntCache = {}
def poissonIntegral(events, rate, tMin, tMax, plot=False):
    
    global poissonIntCache
    xvals = np.linspace(tMin, tMax, 1000)
    dt = xvals[1]-xvals[0]
    tot = 0
    t = tMin
    nev = 0
    allprobs = []
    events = list(events)
    events.sort()
    events.append(tMax)
    for ev in events:
        if ev < tMin:
            continue
        if ev > tMax:
            ev = tMax
        i1 = int((t-tMin) / dt)
        i2 = int((ev-tMin) / dt)
        if nev not in poissonIntCache:
            poissonIntCache[nev] = np.array([1-stats.poisson(rate * x).cdf(nev) for x in xvals])
        probs = poissonIntCache[nev][i1:i2]
        tot += (1./probs).sum()
        allprobs.append(1./probs)
        t = ev
        nev += 1
        if ev == tMax:
            break
        
    if plot:
        y = np.concatenate(allprobs)
        pg.plot(x=xvals[:len(y)], y=y)
    return tot * dt
    #return (1. / poissonProb(events, xvals, rate)).sum() ** 0.5
        
def poissonScoreBlame(ev, rate):
    ## estimate how much each event contributes to the poisson-score of a list of events.
    if len(ev) == 0:
        return []
    pp = []
    for i in range(len(ev)):
        ev2 = list(ev)
        ev2.pop(i)
        #pp.append(poissonScore(ev, rate) / poissonScore(ev2, rate))
        pp1 = 1. / poissonProb(ev, ev[i:], rate)
        pp2 = 1. / poissonProb(ev2, ev[i:], rate)
        pp.append((pp1 / pp2).max())
    ret = np.array(pp)
    assert not any(np.isnan(pp))
    return ret

def poissonIntegralBlame(ev, rate, xMin, xMax):
    ## estimate how much each event contributes to the poisson-integral of a list of events.
    pp = []
    for i in range(len(ev)):
        ev2 = list(ev)
        ev2.pop(i)
        pp1 = poissonIntegral(ev, rate, xMin, xMax)
        pp2 = poissonIntegral(ev2, rate, xMin, xMax)
        pp.append(pp1 / pp2)
    ret = np.array(pp)
    assert not any(np.isnan(pp))
    return ret

#def poissonBlame(ev, rate):
    ### estimate how much each event contributes to the poisson-score of a list of events.
    #ev = list(ev)
    #ps = poissonScore(ev, rate)
    #pp = []
    #while len(ev) > 0:
        #ev.pop(-1)
        #if len(ev) == 0:
            #ps2 = 1.0
        #else:
            #ps2 = poissonScore(ev, rate)
        #pp.insert(0, ps / ps2)
        #ps = ps2
    #return np.array(pp)
    
def productlog(x):
    n = np.arange(1, 30, dtype=float)
    return ((x ** n) * ((-n) ** (n-1)) / scipy.misc.factorial(n)).sum()
    
    
    
def productlog(x, prec=1e-12):
    """
    Stolen from py-fcm:
    Productlog or LambertW function computes principal solution for w in f(w) = w*exp(w).
    """ 
    #  fast estimate with closed-form approximation
    if (x <= 500):
        lxl = np.log(x + 1.0)
        return 0.665 * (1+0.0195*lxl) * lxl + 0.04
    else:
        return np.log(x - 4.0) - (1.0 - 1.0/np.log(x)) * np.log(np.log(x))

def poissonProb(n, t, l):
    """
    For a poisson process, return the probability of seeing at least *n* events in *t* seconds given
    that the process has a mean rate *l* AND the last event occurs at time *t*.
    """
    return stats.poisson(l*t).cdf(n-1)   ## using n-1 corrects for the fact that we _know_ one of the events is at the end.
    
def maxPoissonProb(ev, l):
    """
    For a list of events, compute poissonImp for each event; return the maximum and the index of the maximum.
    """
    pi = poissonProb(np.arange(1, len(ev)+1), ev, l)
    ind = np.argmax(pi)
    #norm = 1. / 2.**(1./len(ev))  ## taking max artificialy increases probability value; re-normalize
    #return pi[ind]/norm, ind
    #return pi[ind]**len(ev), ind   ## raise to power of len(ev) in order to flatten distribution.
    return [pi[ind], ind] + list(pi)
    
#def poissonImp(n, t, l):
    #"""
    #For a poisson process, return the improbability of seeing at least *n* events in *t* seconds given
    #that the process has a mean rate *l* AND the last event occurs at time *t*.
    #"""
    #return 1.0 / (1.0 - stats.poisson(l*t).cdf(n-1))   ## using n-1 corrects for the fact that we _know_ one of the events is at the end.
    ##l = l * t + 1
    ##i = np.arange(0, n+1)
    ##cdf = np.exp(-l) * (l**i / scipy.misc.factorial(i)).sum()
    ##return 1.0 / (1.0 - cdf)

#def maxPoissonImp(ev, l):
    #"""
    #For a list of events, compute poissonImp for each event; return the maximum and the index of the maximum.
    #"""
    #pi = poissonImp(np.arange(1, len(ev)+1), ev, l)
    #ind = np.argmax(pi)
    #return pi[ind], ind
    
#def timeOfPoissonImp(p, n, l, guess=0.1):
    #"""
    #Solve p == poissonImp(n, t, l) for t
    #"""
    #def erf(t):
        #return p - poissonImp(n, t, l)
    #return scipy.optimize.leastsq(erf, guess)[0][0]
    
#def polyRedist(v, x):
    #return v[0] + v[1] * x + v[2] * x**2 + v[3] * x**3 + v[4] * x**4

#def polyRedistFit(ev1, ev2):
    #"""
    #Find polynomial coefficients mapping ev1 onto ev2
    #"""
    #h2 = np.histogram(ev2, bins=200)
    #def err(v):
        #h1 = np.histogram(polyRedist(v, ev1), bins=200)
        ##print v, ((h2[0]-h1[0])**2).sum()
        #return h2[0] - h1[0]
    #return scipy.optimize.leastsq(err, x0=(0, 1, 0, 0, 0))
    
#def ellipseRedist(v, x):
    #x0, x1 = v
    #xp = x0 + x * (x1 - x0)
    #y0 = -(1-x0**2)**0.5
    #y1 = -(1-x1**2)**0.5
    #yp = -(1-xp**2)**0.5
    #y = (yp - y0) / (y1 - y0)
    #return y

#def ellipseRedistFit(ev1, ev2, **kwds):
    #"""
    #Find circular coefficients mapping ev1 onto ev2
    #"""
    #h2 = np.histogram(ev2, bins=200)
    #def err(v):
        #print v
        #v = (v[0], min(v[1], 0.9999999))
        #h1 = np.histogram(ellipseRedist(v, ev1), bins=200)
        #return ((h2[0][-50:] - h1[0][-50:])**2).sum()
    #return scipy.optimize.fmin(err, x0=(0.995, 0.9995), **kwds)

#def poissonImpInv(x, l):
    #return -(2 + productlog(-x / np.exp(3))) / l

rate = 15.
trials = 2000000

# create a seties of poisson event trains with n=1
#ev1 = np.vstack([poissonProcess(rate=rate, n=1) for i in xrange(trials)])
#mpi1 = np.array([maxPoissonImp(e, rate) for e in ev1])


# create a series of poisson event trains with n=2
app = pg.mkQApp()
plt = pg.plot()
pp = []
mpp = []
for n in [2]:#,3,4,5]:
    ev2 = np.vstack([poissonProcess(rate=rate, n=n) for i in xrange(trials)])
    #pi2 = np.array([poissonImp(n, e[-1], rate) for e in ev2])
    #mpi2 = np.array([maxPoissonImp(e, rate) for e in ev2])
    #mpi20 = mpi2[mpi2[:,1]==0][:,0]
    #mpi21 = mpi2[mpi2[:,1]==1][:,0]
    app.processEvents()
    pp2 = np.array([poissonProb(n, e[-1], rate) for e in ev2])
    app.processEvents()
    mpp2 = np.array([maxPoissonProb(e, rate) for e in ev2])

    #break
    
    #print "\nPoisson improbability (n=%d):" % n
    #for i in range(1,4):
        #print "  %d: %0.2f%%" % (10**i, (pi2>10**i).sum() * 100. / trials)
    #print "Max poisson improbability (n=%d):" % n
    #for i in range(1,4):
        #print "  %d: %0.2f%%" % (10**i, (mpi2[:,0]>10**i).sum() * 100. / trials)
    print "\nPoisson probability (n=%d):" % n
    for i in range(1,4):
        thresh = 1.-10**-i
        print "  %0.2f: %0.2f%%" % (thresh, (pp2>thresh).sum() * 100. / trials)
    print "Max poisson probability (n=%d):" % n
    for i in range(1,4):
        thresh = 1.-10**-i
        print "  %0.2f: %0.2f%%" % (thresh, (mpp2[:,0]>thresh).sum() * 100. / trials)


    h = np.histogram(pp2, bins=100)
    plt.plot(h[1][1:], h[0], pen='g')
    h = np.histogram(mpp2[:,0], bins=100)
    plt.plot(h[1][1:], h[0], pen='y')
    app.processEvents()
    
    pp.append(pp2)
    mpp.append(mpp2)


mpp1 = mpp[0][mpp[0][:,1]==0]
mpp2 = mpp[0][mpp[0][:,1]==1]
h1 = np.histogram(mpp1[:,3], bins=100)
h2 = np.histogram(mpp1[:,2], bins=100)
h3 = np.histogram(mpp2[:,2], bins=100)
h4 = np.histogram(mpp2[:,3], bins=100)
pg.plot(h1[1][1:], (h2[0]+h4[0])-(h1[0]+h3[0]))

raise SystemExit(0)
























## show that poissonProcess works as expected
#plt = pg.plot()
#for rate in [3, 10, 20]:
    #d1 = np.random.poisson(rate, size=100000)
    #h1 = np.histogram(d1, bins=range(d1.max()+1))

    #d2 = np.array([len(poissonProcess(rate, 1)) for i in xrange(100000)])
    #h2 = np.histogram(d2, bins=range(d2.max()+1))

    #plt.plot(h2[1][1:], h2[0], pen='g', symbolSize=3)
    #plt.plot(h1[1][1:], h1[0], pen='r', symbolSize=3)


## assign post-score to a series of events
#rate = 20.
#ev = poissonProcess(rate, 1.0)
#times = np.linspace(0.0, 1.0, 1000)
#prob = poissonProb(ev, times, rate)
#plt = pg.plot()

#for i in range(5):
    #prob = poissonProb(ev, times, rate)
    #c = plt.plot(x=times, y=1./prob, pen=(i,7))
    #c.setZValue(-i)
    #ev = np.append(ev, 0.06+i*0.01)
    #ev.sort()

    
#def recursiveBlame(ev, inds, rate, depth=0):
    #print "  "*depth, "start:", zip(inds, ev)
    #score = poissonScore(ev, rate)
    ##print "score:"
    #subScores = {}
    #for i in range(len(ev)):
        #ev2 = list(ev)
        #ev2.pop(i)
        #print "  "*depth, "check:", ev2
        #subScores[inds[i]] = score / poissonScore(ev2, rate)
    #print "  " * depth, "scores:", subScores
    
    
    #ev2 = [ev[i] for i in range(len(ev)) if subScores[inds[i]] > 1.0]
    #inds2 = [inds[i] for i in range(len(ev)) if subScores[inds[i]] > 1.0]
    #print "  "*depth, "passed:", zip(inds2, ev2)
    #if len(ev2) < 3:
        #return subScores
        
    #correctedScores = {}
    #for i in range(len(ev2)):
        #print "  "*depth, "remove", inds2[i], ':'
        #ev3 = list(ev2)
        #ev3.pop(i)
        #inds3 = list(inds2)
        #inds3.pop(i)
        #newScores = recursiveBlame(ev3, inds3, rate, depth+2)
        #if newScores is None:
            #continue
        #print "  "*depth, "compute correction:"
        #correction = 1.0
        #for j in range(len(ev3)):
            #c = subScores[inds3[j]] / newScores[inds3[j]]
            #correction *= c
            #print "  "*depth, inds3[j], c
        #correctedScores[inds2[i]] = subScores[inds2[i]] * correction
        #print "  "*depth, "final score:", inds2[i], correctedScores[inds2[i]]
        
        
        
    #return correctedScores
    
    
## Attempt to assign a post-probability to each event
#rate = 3.
#plt = pg.plot(name='Event Score')
#allev1 = []
#allev2 = []
#for i in range(10): ## reps
    #ev = poissonProcess(rate, 1.0)
    #allev1.append(ev)
    #colors = ['g'] * len(ev)
    #for i in range(3):  ## insert 4 events
        #ev = np.append(ev, 0.02 + np.random.gamma(shape=1, scale=0.01))
        #colors.append('w')
    #ev = np.append(ev, 0.07)
    #colors.append('w')
    #ev = np.append(ev, 0.15)
    #colors.append('w')
    
    
    
    #allev2.append(ev)
    #pp = poissonBlame(ev, rate)
    #print len(ev), len(pp), len(colors)
    #plt.plot(x=ev, y=pp, pen=None, symbol='o', symbolBrush=colors).setOpacity(0.5)

#allev1 = np.concatenate(allev1)
#allev2 = np.concatenate(allev2)
#h = np.histogram(allev1, bins=100)
#plt = pg.plot(h[1][1:], h[0], name='PSTH')
#h = np.histogram(allev2, bins=100)
#plt.plot(h[1][1:], h[0])

#print ev
#recursiveBlame(ev, list(range(len(ev))), rate)

app = pg.mkQApp()
#con = pyqtgraph.console.ConsoleWidget()
#con.show()
#con.catchAllExceptions()



## Test ability of poissonScore to predict proability of seeing false positives

with mp.Parallelize(tasks=[2, 2, 2, 2, 5, 5, 5, 5, 10, 10, 10, 10, 20, 20, 20, 20]) as tasker:
    #np.random.seed(os.getpid() ^ int(time.time()*100))  ## make sure each fork gets its own random seed
    for rate in tasker:
        #rate = 5.
        tMax = 1.0
        totals = [0,0,0,0,0,0]
        pptotals = [0,0,0,0,0,0]
        trials = 10000
        for i in xrange(trials):
            events = poissonProcess(rate, tMax)
            ##prob = 1.0 / poissonProb(events, [tMax], rate)[0]
            ##prob = 1.0 / (1.0 - stats.poisson(rate*tMax).cdf(len(events)))  ## only gives accurate predictions for large rate
            #prob = 1.0 / (1.0 - stats.poisson(rate*(events[-1]+(1./rate) if len(events) > 0 else tMax)).cdf(len(events)))  ## only gives accurate predictions for large rate
            #score = poissonIntegral(events, rate, 0.005, 0.3)
            score = poissonScore(events, rate)
            for i in range(1,6):
                if score > 10**i:
                    totals[i] += 1
                #if prob > 10**i:
                    #pptotals[i] += 1
        print "spont rate:", rate
        print "False negative scores:"
        for i in range(1,6):
            print "   > %d: %d (%0.2f%%)" % (10**i, totals[i], 100*totals[i]/float(trials))
        #print "False negative probs:"
        #for i in range(1,6):
            #print "   > %d: %d (%0.2f%%)" % (10**i, pptotals[i], 100*pptotals[i]/float(trials))

raise Exception()

## Create a set of test cases:

reps = 30
spontRate = 3.
miniAmp = 1.0
tMax = 0.5

def randAmp(n=1, quanta=1):
    return np.random.gamma(4., size=n) * miniAmp * quanta / 4.

## create a standard set of spontaneous events
spont = []
for i in range(reps):
    times = poissonProcess(spontRate, tMax)
    amps = randAmp(len(times))  ## using scale=4 gives a nice not-quite-gaussian distribution
    source = ['spont'] * len(times)
    spont.append((times, amps, source))


def spontCopy(i, extra):
    times, amps, source = spont[i]
    ev = np.zeros(len(times)+extra, dtype=[('time', float), ('amp', float), ('source', object)])
    ev['time'][:len(times)] = times
    ev['amp'][:len(times)] = amps
    ev['source'][:len(times)] = source
    return ev
    
## copy spont. events and add on evoked events
tests = [[] for i in range(7)]
for i in range(reps):
    ## Test 0: no evoked events
    tests[0].append(spontCopy(i, 0))

    ## Test 1: 1 extra event, single quantum, short latency
    ev = spontCopy(i, 1)
    ev[-1] = (0.01, 1, 'evoked')
    tests[1].append(ev)

    ## Test 2: 2 extra events, single quantum, short latency
    ev = spontCopy(i, 2)
    for j, t in enumerate([0.01, 0.015]):
        ev[-(j+1)] = (t, 1, 'evoked')
    tests[2].append(ev)

    ## Test 3: 4 extra events, single quantum, short latency
    ev = spontCopy(i, 4)
    for j,t in enumerate([0.01, 0.015, 0.024, 0.04]):
        ev[-(j+1)] = (t, 1, 'evoked')
    tests[3].append(ev)

    ## Test 4: 3 extra events, single quantum, long latency
    ev = spontCopy(i, 3)
    for j,t in enumerate([0.07, 0.10, 0.15]):
        ev[-(j+1)] = (t, 1, 'evoked')
    tests[4].append(ev)

    ## Test 5: 1 extra event, 2 quanta, short latency
    ev = spontCopy(i, 1)
    ev[-1] = (0.01, 2, 'evoked')
    tests[5].append(ev)

    ## Test 6: 1 extra event, 3 quanta, long latency
    ev = spontCopy(i, 1)
    ev[-1] = (0.05, 3, 'evoked')
    tests[6].append(ev)

#raise Exception()

## Analyze and plot all:

win = pg.GraphicsWindow(border=0.3)
with pg.ProgressDialog('processing..', maximum=len(tests)) as dlg:
    for i in range(len(tests)):
        first = (i == 0)
        last = (i == len(tests)-1)
        
        if first:
            evLabel = win.addLabel('Event amplitude', angle=-90, rowspan=len(tests))
        evplt = win.addPlot()
        
        if first:
            scoreLabel = win.addLabel('Poisson Score', angle=-90, rowspan=len(tests))
        scoreplt = win.addPlot()
        
        if first:
            intLabel = win.addLabel('Poisson Integral', angle=-90, rowspan=len(tests))
        intplt = win.addPlot()
        
        if first:
            scoreBlameLabel = win.addLabel('Poisson Score Blame', angle=-90, rowspan=len(tests))
        scoreblameplt = win.addPlot()
        
        if first:
            intBlameLabel = win.addLabel('Poisson Integral Blame', angle=-90, rowspan=len(tests))
        intblameplt = win.addPlot()
        
        if first:
            evplt.register('EventPlot1')
            scoreplt.register('ScorePlot1')
            intplt.register('IntegralPlot1')
            scoreblameplt.register('ScoreBlamePlot1')
            intblameplt.register('IntegralBlamePlot1')
        else:
            evplt.setXLink('EventPlot1')
            scoreplt.setXLink('ScorePlot1')
            intplt.setXLink('IntegralPlot1')
            scoreblameplt.setXLink('ScoreBlamePlot1')
            intblameplt.setXLink('IntegralBlamePlot1')
            
        scoreplt.setLogMode(False, True)
        intplt.setLogMode(False, True)
        #diag = pg.InfiniteLine(angle=45)
        #scoreplt.addItem(diag)
        #scoreplt.hideAxis('left')
        scoreplt.hideAxis('bottom')
        intplt.hideAxis('bottom')
        
        
        for j in range(reps):
            ev = tests[i][j]
            spont = tests[0][j]
            colors = [(0,255,0,50) if source=='spont' else (255,255,255,50) for source in ev['source']]
            evplt.plot(x=ev['time'], y=ev['amp'], pen=None, symbolBrush=colors, symbol='d', symbolSize=8, symbolPen=None)
            
            #print ev['time']
            score1 = poissonScore(ev['time'], spontRate)
            score2 = poissonScore(spont['time'], spontRate)
            scoreplt.plot(x=[j], y=[score1], pen=None, symbol='o', symbolBrush=(255,255,255,100))
            scoreplt.plot(x=[j], y=[score2], pen=None, symbol='o', symbolBrush=(0,255,0,100))

            xMin = 0.005
            xMax = 0.3
            int1 = poissonIntegral(ev['time'], spontRate, xMin, xMax)
            int2 = poissonIntegral(spont['time'], spontRate, xMin, xMax)
            intplt.plot(x=[j], y=[int1], pen=None, symbol='o', symbolBrush=(255,255,255,100))
            intplt.plot(x=[j], y=[int2], pen=None, symbol='o', symbolBrush=(0,255,0,100))
            
            blame = poissonScoreBlame(ev['time'], spontRate)
            scoreblameplt.plot(x=ev['time'], y=blame, pen=None, symbolBrush=colors, symbol='d', symbolSize=8, symbolPen=None)
            
            blame = poissonIntegralBlame(ev['time'], spontRate, xMin, xMax)
            intblameplt.plot(x=ev['time'], y=blame, pen=None, symbolBrush=colors, symbol='d', symbolSize=8, symbolPen=None)
            
            evplt.hideAxis('bottom')
            #scoreplt.hideAxis('bottom')
            if last:
                evplt.showAxis('bottom')
                evplt.setLabel('bottom', 'Event time', 's')
                #scoreplt.showAxis('bottom')
                #scoreplt.setLabel('bottom', 'Spontaneous Score')
            
        dlg += 1
        if dlg.wasCanceled():
            break
            
        win.nextRow()
    
    
    






